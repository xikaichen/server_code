"""
报告分析服务模块
处理报告AI分析的业务逻辑
"""
from app.utils.database import SessionLocal
from app.models.report import Report
from app.services.ai_analysis import (
    get_ai_analysis,
    CHECK_TYPE_GUIDE_PROMPTS,
    CHECK_TYPE_EXPERT_PROMPTS,
)
from concurrent.futures import ThreadPoolExecutor
import json
import logging

logger = logging.getLogger(__name__)


def process_report_analysis(report_id: int):
    """
    异步处理报告AI分析任务
    
    重要：重试机制如何触发
    =====================
    1. 如果函数正常执行完成（没有抛出异常），任务成功，不会重试
    2. 如果函数抛出异常（Exception），任务失败，RQ 会自动触发重试
    3. 如果函数执行超时（超过 job_timeout），任务失败，RQ 会自动触发重试
    4. 如果 Worker 进程崩溃，正在执行的任务会失败，RQ 会自动触发重试
    
    重试示例：
    ========
    假设 get_ai_analysis() 调用失败抛出异常：
    - 第1次：异常 → RQ 捕获 → 等待60秒 → 自动重试
    - 第2次：异常 → RQ 捕获 → 等待60秒 → 自动重试
    - 第3次：异常 → RQ 捕获 → 等待60秒 → 自动重试
    - 第4次：异常 → RQ 捕获 → 达到最大重试次数 → 永久失败
    
    注意：
    - 不要在这里手动捕获所有异常并返回，否则 RQ 认为任务成功，不会重试
    - 应该让真正的异常抛出，让 RQ 来处理重试
    - 只有确定不需要重试的错误（如参数错误），才应该捕获并返回
    
    Args:
        report_id: 报告ID
    """
    db = SessionLocal()
    try:
        logger.info(f"开始处理报告 {report_id} 的AI分析任务")
        # 获取报告
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            print(f"报告 {report_id} 不存在")
            return
        
        # 如果是常规检查（check_type == 1），不需要AI分析
        if report.check_type == 1:
            report.status = 'completed'
            db.commit()
            return
        
        # 获取提示词
        guide_prompt = CHECK_TYPE_GUIDE_PROMPTS.get(report.check_type)
        if not guide_prompt:
            report.status = 'failed'
            db.commit()
            print(f"不支持的检查类型: {report.check_type}")
            return
        
        # 构造单眼图像的提示消息
        def build_messages(image_base64: str, text_prompt: str):
            return [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": text_prompt
                        },
                    ]
                }
            ]
        
        # 初始化检查结果
        check_result = {
            'left_eye_analyse': '',
            'right_eye_analyse': '',
            'left_eye_status': '',
            'right_eye_status': ''
        }
        
        # 构造左右眼分析消息
        left_eye_quest_messages = build_messages(report.left_eye_image, guide_prompt)
        right_eye_quest_messages = build_messages(report.right_eye_image, guide_prompt)
        
        # 并行发起左右眼分析
        with ThreadPoolExecutor(max_workers=2) as executor:
            left_future = executor.submit(get_ai_analysis, left_eye_quest_messages)
            right_future = executor.submit(get_ai_analysis, right_eye_quest_messages)
            left_eye_analyse = left_future.result().strip()
            right_eye_analyse = right_future.result().strip()
        
        check_result['left_eye_analyse'] = left_eye_analyse
        check_result['right_eye_analyse'] = right_eye_analyse
        
        # 构造状态判断消息
        def build_status_messages(image_base64: str, eye_analyse: str):
            return [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": (
                                '请结合该眼部图像与文字分析，判断该检查结果是正常还是异常，仅回答"正常"或"异常"：\n'
                                + eye_analyse
                            )
                        }
                    ]
                }
            ]
        
        # 并行判断左右眼检查状态
        left_status_messages = build_status_messages(report.left_eye_image, left_eye_analyse)
        right_status_messages = build_status_messages(report.right_eye_image, right_eye_analyse)
        with ThreadPoolExecutor(max_workers=2) as executor:
            left_status_future = executor.submit(get_ai_analysis, left_status_messages)
            right_status_future = executor.submit(get_ai_analysis, right_status_messages)
            left_eye_status = left_status_future.result().strip()
            right_eye_status = right_status_future.result().strip()
        
        check_result['left_eye_status'] = left_eye_status
        check_result['right_eye_status'] = right_eye_status
        
        # 组合对话上下文，供专家分析阶段参考
        all_quest_messages = []
        all_quest_messages += left_eye_quest_messages
        all_quest_messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": left_eye_analyse
                    },
                ]
            }
        )
        all_quest_messages += right_eye_quest_messages
        all_quest_messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": right_eye_analyse
                    },
                ]
            }
        )
        
        # 获取专家分析提示词
        expert_prompt = CHECK_TYPE_EXPERT_PROMPTS.get(
            report.check_type, "根据以上数据，给出专业的眼科分析"
        )
        
        # 引导AI结合左右眼结果得出专家分析
        expert_analyse_content = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": expert_prompt
                    },
                ]
            }
        ]
        
        all_quest_messages += expert_analyse_content
        
        # 获取专家分析
        expert_analyse = get_ai_analysis(all_quest_messages)
        
        # 更新报告
        report.expert_analyse = expert_analyse
        report.check_result = json.dumps(check_result)
        report.status = 'completed'
        db.commit()
        
        logger.info(f"报告 {report_id} AI分析完成")
        
    except Exception as e:
        # 重要：这里抛出异常，让 RQ 捕获并触发自动重试
        # 如果捕获异常后不抛出，RQ 会认为任务成功完成，不会重试
        logger.error(f"处理报告 {report_id} 时发生错误: {e}", exc_info=True)
        
        # 更新状态为失败（仅在数据库操作成功时）
        # 注意：即使这里更新失败，异常仍然会抛出，RQ 仍会重试
        try:
            report = db.query(Report).filter(Report.id == report_id).first()
            if report:
                report.status = 'failed'
                db.commit()
        except Exception as db_error:
            logger.error(f"更新报告 {report_id} 状态失败: {db_error}")
        
        # 重新抛出异常，让 RQ 知道任务失败，触发自动重试
        # 这是关键！如果不抛出，RQ 认为任务成功，不会重试
        raise
    finally:
        db.close()


__all__ = [
    "process_report_analysis",
]

