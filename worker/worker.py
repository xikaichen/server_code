"""
RQ Worker 启动脚本
用于处理后台异步任务

生产环境部署（宝塔面板）：
1. 在宝塔面板 -> 软件商店 -> 安装 Supervisor 管理器
2. 添加守护进程：
   - 名称：rq-worker
   - 启动用户：root 或 www
   - 运行目录：项目根目录（或包含项目的父目录，根据实际情况）
   - 启动命令（推荐使用启动脚本）：
     bash worker/start_worker.sh
     或
     /bin/bash worker/start_worker.sh
   
   如果使用宝塔 Python 项目管理器，需要先激活环境，启动脚本已包含此逻辑。
   
   其他方式（备选）：
   - 使用完整 Python 路径：/www/server/python/项目环境路径/bin/python worker/worker.py
   - 直接使用 python（不推荐，可能有 PATH 问题）：python worker/worker.py

   - 日志文件：worker/logs/worker.log（会自动创建）

开发环境启动：
    python worker/worker.py
"""
import os
import sys
import signal
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# 将项目根目录添加到 Python 路径，确保可以导入 app 模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rq import Worker, Queue
from rq.worker import SimpleWorker
from rq.logutils import setup_loghandlers
from app.utils.database import get_redis_client_for_rq
from app.config import settings

# 确保日志目录存在（在 worker 目录下）
LOG_DIR = Path(__file__).parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'worker.log'

# 配置日志：同时输出到控制台和文件
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 清除已有的处理器
logger.handlers.clear()

# 控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(console_formatter)

# 文件处理器（带轮转）
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,  # 保留5个备份文件
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)

# 添加处理器
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# 队列名称配置
QUEUE_NAMES = ['report_analysis']  # 可以监听多个队列


def create_redis_connection():
    """创建 Redis 连接"""
    return get_redis_client_for_rq()


def create_queues(redis_conn):
    """创建队列列表"""
    return [Queue(name, connection=redis_conn) for name in QUEUE_NAMES]


def signal_handler(signum, frame):
    """处理退出信号，实现优雅关闭"""
    logger.info(f"收到信号 {signum}，正在优雅关闭 worker...")
    sys.exit(0)


def main():
    """主函数：启动 RQ Worker"""
    logger.info("=" * 60)
    logger.info("RQ Worker 启动中...")
    logger.info(f"项目根目录: {PROJECT_ROOT}")
    logger.info(f"日志文件: {LOG_FILE.absolute()}")
    logger.info("=" * 60)
    
    # 注册信号处理器，实现优雅关闭
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 创建 Redis 连接
        redis_conn = create_redis_connection()
        
        # 测试连接
        redis_conn.ping()
        redis_url = f"{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        logger.info(f"✓ 成功连接到 Redis: {redis_url}")
        
        # 创建队列
        queues = create_queues(redis_conn)
        queue_names = ', '.join(QUEUE_NAMES)
        logger.info(f"✓ 监听队列: {queue_names}")
        
        # 配置 RQ 日志
        setup_loghandlers(logging.INFO)
        
        # 根据平台选择 Worker 类型
        if sys.platform == 'win32':
            logger.info("使用 SimpleWorker（Windows 线程模式）")
            worker = SimpleWorker(queues, connection=redis_conn)
        else:
            logger.info("使用 Worker（Unix 进程 fork 模式）")
            worker = Worker(queues, connection=redis_conn)
        
        logger.info("=" * 60)
        logger.info("RQ Worker 已启动，开始处理任务...")
        logger.info("提示：Worker 停止后，队列中的任务仍在 Redis 中，重启后会继续处理")
        logger.info("=" * 60)
        
        # 开始工作
        worker.work()
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止 worker...")
    except Exception as e:
        logger.error(f"Worker 启动失败: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Worker 已停止")


if __name__ == '__main__':
    main()

