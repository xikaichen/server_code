"""
异步任务处理模块
使用RQ（Redis Queue）处理后台任务

关于任务恢复和重试：
1. 队列中的任务（queued）：worker 重启后会自动继续处理
2. 执行中的任务（started）：worker 崩溃时会变成 failed，需要配置重试机制
3. 失败的任务（failed）：不会自动重试，需要手动配置重试逻辑
"""
from rq import Queue, Retry
from rq.job import Job
from app.utils.database import get_redis_client_for_rq
from app.services.report_analysis import process_report_analysis
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# 延迟初始化任务队列
_task_queue = None
_redis_connection = None

def get_redis_connection():
    """获取 Redis 连接（延迟初始化，支持连接复用）"""
    global _redis_connection
    if _redis_connection is None:
        _redis_connection = get_redis_client_for_rq()
    return _redis_connection

def get_task_queue():
    """
    获取任务队列实例（延迟初始化）
    
    使用连接复用，避免每次创建新连接
    
    重要：任务持久化机制
    ===================
    1. 任务信息存储在 Redis 中，而不是 Worker 的内存中
    2. 当任务入队时，RQ 会将任务信息序列化后存储到 Redis：
       - 队列列表：rq:queue:report_analysis (存储任务 ID 列表)
       - 任务详情：rq:job:{job_id} (存储任务的完整信息)
    3. Worker 停止时，任务仍然在 Redis 中
    4. 新的 Worker 启动时，会从 Redis 读取队列，继续处理任务
    5. 这就是为什么 Worker 重启后任务不会丢失的原因
    """
    global _task_queue
    if _task_queue is None:
        redis_client = get_redis_connection()
        _task_queue = Queue('report_analysis', connection=redis_client)
    return _task_queue


def enqueue_report_analysis(report_id: int):
    """
    将报告分析任务加入队列，并配置重试和超时
    
    RQ 重试机制工作原理：
    ====================
    1. 当任务执行失败（抛出异常）时，RQ 会自动检查任务是否配置了 retry
    2. 如果配置了 retry，RQ 会：
       - 记录当前重试次数
       - 等待指定的延迟时间（interval）
       - 将任务重新放回队列（状态从 failed 变回 queued）
       - Worker 会重新从队列中取出任务执行
    3. 如果重试次数达到最大值（max），任务会永久失败，不再重试
    
    重试流程示例：
    =============
    第1次执行：失败 → 等待60秒 → 第2次重试
    第2次执行：失败 → 等待60秒 → 第3次重试  
    第3次执行：失败 → 等待60秒 → 第4次重试（最后一次）
    第4次执行：失败 → 永久失败，不再重试
    
    注意：
    - 只有抛出异常的任务才会触发重试
    - 正常返回（即使返回错误状态）不会触发重试
    - Worker 崩溃导致的任务失败也会触发重试
    - 任务执行途中 Worker 被关闭，新 Worker 启动时会自动清理僵尸任务并触发重试
    
    Args:
        report_id: 报告ID
        
    Returns:
        Job: RQ Job 实例
    """
    queue = get_task_queue()
    
    # 配置重试机制
    # max: 最大重试次数（不包括首次执行，所以总共会执行 max+1 次）
    # interval: 每次失败后等待多少秒再重试
    retry = Retry(
        max=settings.RQ_JOB_RETRY_MAX,  # 最多重试3次（总共执行4次：1次初始 + 3次重试）
        interval=settings.RQ_JOB_RETRY_DELAY  # 每次失败后等待60秒再重试
    )
    
    # 入队任务，配置超时和重试
    job = queue.enqueue(
        process_report_analysis,
        report_id,
        job_timeout=settings.RQ_JOB_TIMEOUT,  # 任务超时时间（30分钟）
        result_ttl=settings.RQ_JOB_RESULT_TTL,  # 成功结果保留时间（24小时）
        failure_ttl=settings.RQ_JOB_FAILURE_TTL,  # 失败任务保留时间（24小时）
        retry=retry,  # 重试配置：这是关键！告诉 RQ 这个任务失败后要自动重试
        job_id=f'report_analysis_{report_id}',  # 设置任务ID，便于追踪和去重
    )
    
    logger.info(f"报告 {report_id} 的分析任务已加入队列，Job ID: {job.id}，已配置自动重试（最多{settings.RQ_JOB_RETRY_MAX}次）")
    return job

