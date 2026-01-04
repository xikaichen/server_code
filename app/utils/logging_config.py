"""
集中式日志配置模块
为整个应用程序提供统一的日志配置
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from app.config import settings


# 日志目录和文件配置
LOG_DIR = Path(__file__).parent.parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)
APP_LOG_FILE = LOG_DIR / 'app.log'
ERROR_LOG_FILE = LOG_DIR / 'error.log'

# 日志格式
LOG_FORMAT = '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logging():
    """
    配置应用程序的日志系统
    
    日志输出：
    1. 控制台：INFO 及以上级别
    2. app.log：所有日志（INFO 及以上）
    3. error.log：仅错误日志（ERROR 及以上）
    
    日志轮转：
    - 单个文件最大 10MB
    - 保留 5 个备份文件
    """
    # 获取根日志记录器
    root_logger = logging.getLogger()
    
    # 设置根日志级别
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    root_logger.setLevel(log_level)
    
    # 清除已有的处理器（避免重复配置）
    root_logger.handlers.clear()
    
    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # 1. 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 2. 应用日志文件处理器（所有日志）
    app_file_handler = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    app_file_handler.setLevel(logging.INFO)
    app_file_handler.setFormatter(formatter)
    root_logger.addHandler(app_file_handler)
    
    # 3. 错误日志文件处理器（仅错误）
    error_file_handler = RotatingFileHandler(
        ERROR_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    root_logger.addHandler(error_file_handler)
    
    # 配置第三方库的日志级别（避免过多日志）
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    # 记录日志配置完成
    root_logger.info("=" * 60)
    root_logger.info("日志系统初始化完成")
    root_logger.info(f"日志目录: {LOG_DIR.absolute()}")
    root_logger.info(f"应用日志: {APP_LOG_FILE.absolute()}")
    root_logger.info(f"错误日志: {ERROR_LOG_FILE.absolute()}")
    root_logger.info(f"日志级别: {logging.getLevelName(log_level)}")
    root_logger.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return logging.getLogger(name)

