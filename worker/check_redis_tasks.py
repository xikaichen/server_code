"""
查看 Redis 中 RQ 任务状态的工具脚本

使用方法：
    python worker/check_redis_tasks.py
"""
import sys
from pathlib import Path

# 将项目根目录添加到 Python 路径，确保可以导入 app 模块
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.utils.database import get_redis_client_for_rq
from rq import Queue
from rq.job import Job
from app.config import settings
import json

def check_queue_status():
    """检查队列状态"""
    redis_conn = get_redis_client_for_rq()
    queue = Queue('report_analysis', connection=redis_conn)
    
    print("=" * 60)
    print("RQ 任务队列状态")
    print("=" * 60)
    print(f"队列名称: report_analysis")
    print(f"队列中的任务数: {len(queue)}")
    print()
    
    # 查看队列中的任务
    if len(queue) > 0:
        print("队列中的任务:")
        print("-" * 60)
        for i, job_id in enumerate(queue.job_ids, 1):
            try:
                job = Job.fetch(job_id, connection=redis_conn)
                print(f"{i}. 任务 ID: {job_id}")
                print(f"   状态: {job.get_status()}")
                print(f"   创建时间: {job.created_at}")
                if job.enqueued_at:
                    print(f"   入队时间: {job.enqueued_at}")
                if job.started_at:
                    print(f"   开始时间: {job.started_at}")
                if job.ended_at:
                    print(f"   结束时间: {job.ended_at}")
                print()
            except Exception as e:
                print(f"{i}. 任务 ID: {job_id} (无法获取详情: {e})")
                print()
    else:
        print("队列为空，没有待处理的任务")
        print()
    
    # 查看失败的任务
    try:
        failed_queue = Queue('failed', connection=redis_conn)
        failed_count = len(failed_queue)
        if failed_count > 0:
            print("失败的任务:")
            print("-" * 60)
            for i, job_id in enumerate(failed_queue.job_ids[:10], 1):  # 只显示前10个
                try:
                    job = Job.fetch(job_id, connection=redis_conn)
                    print(f"{i}. 任务 ID: {job_id}")
                    print(f"   失败时间: {job.ended_at}")
                    if job.exc_info:
                        # 截取异常信息的前200个字符
                        exc_info = job.exc_info[:200] + "..." if len(job.exc_info) > 200 else job.exc_info
                        print(f"   异常信息: {exc_info}")
                    print()
                except Exception as e:
                    print(f"{i}. 任务 ID: {job_id} (无法获取详情: {e})")
                    print()
            if failed_count > 10:
                print(f"... 还有 {failed_count - 10} 个失败任务")
        else:
            print("没有失败的任务")
    except Exception as e:
        print(f"无法获取失败队列: {e}")
    
    print()
    print("=" * 60)
    print("提示：")
    print("1. 任务信息存储在 Redis 中，Worker 停止后任务不会丢失")
    print("2. 队列中的任务会在 Worker 启动时自动处理")
    print("3. 使用 redis-cli 可以查看原始数据：")
    print(f"   redis-cli -h {settings.REDIS_HOST} -p {settings.REDIS_PORT} -n {settings.REDIS_DB}")
    print("   > LRANGE rq:queue:report_analysis 0 -1")
    print("=" * 60)

if __name__ == '__main__':
    try:
        check_queue_status()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

