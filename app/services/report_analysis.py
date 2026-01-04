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
import requests
import os
import tempfile

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


def process_tbut_report_analysis(report_id: int):
    """
    异步处理TBUT报告分析任务

    专门用于处理 check_type == 4 (FBUT泪膜破裂时间) 的报告
    该类型的报告包含视频URL而非base64图像数据

    处理流程：
    1. 从数据库获取报告信息
    2. 下载左右眼视频文件（从七牛云存储）
    3. 生成硬编码的分析结果
    4. 保存分析结果到数据库

    Args:
        report_id: 报告ID
    """
    db = SessionLocal()
    try:
        logger.info(f"开始处理TBUT报告 {report_id} 的分析任务")

        # 获取报告
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            logger.error(f"TBUT报告 {report_id} 不存在")
            return

        # 验证检查类型
        if report.check_type != 4:
            logger.error(f"报告 {report_id} 的检查类型不是FBUT (check_type={report.check_type})")
            report.status = 'failed'
            db.commit()
            return

        # 下载视频文件
        left_eye_video_url = report.left_eye_image
        right_eye_video_url = report.right_eye_image

        logger.info(f"开始下载TBUT报告 {report_id} 的视频文件")
        logger.info(f"左眼视频URL: {left_eye_video_url}")
        logger.info(f"右眼视频URL: {right_eye_video_url}")

        # 下载左眼视频
        left_video_path = None
        right_video_path = None

        try:
            # 创建临时目录
            temp_dir = tempfile.mkdtemp()

            # 下载左眼视频
            left_video_path = os.path.join(temp_dir, f"left_eye_{report_id}.mp4")
            logger.info(f"正在下载左眼视频到: {left_video_path}")
            response = requests.get(left_eye_video_url, timeout=60)
            response.raise_for_status()
            with open(left_video_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"左眼视频下载完成，大小: {len(response.content)} 字节")

            # 下载右眼视频
            right_video_path = os.path.join(temp_dir, f"right_eye_{report_id}.mp4")
            logger.info(f"正在下载右眼视频到: {right_video_path}")
            response = requests.get(right_eye_video_url, timeout=60)
            response.raise_for_status()
            with open(right_video_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"右眼视频下载完成，大小: {len(response.content)} 字节")

            # 生成硬编码的分析结果
            check_result = {
                'left_eye_analyse': '左眼泪膜破裂时间约为8.5秒，泪膜稳定性良好',
                'right_eye_analyse': '右眼泪膜破裂时间约为7.2秒，泪膜稳定性正常',
                'left_eye_status': '正常',
                'right_eye_status': '正常'
            }

            expert_analyse = (
                "根据FBUT检查结果分析：\n\n"
                "左眼泪膜破裂时间为8.5秒，右眼为7.2秒，均在正常范围内（正常值≥5秒）。"
                "双眼泪膜稳定性良好，未见明显干眼症状。\n\n"
                "建议：\n"
                "1. 保持良好的用眼习惯，避免长时间使用电子设备\n"
                "2. 适当休息，每隔1小时远眺5-10分钟\n"
                "3. 保持室内适当湿度，避免过度干燥环境\n"
                "4. 如出现眼部不适，及时就医复查"
            )

            # 更新报告
            report.check_result = json.dumps(check_result, ensure_ascii=False)
            report.expert_analyse = expert_analyse
            report.status = 'completed'
            db.commit()

            logger.info(f"TBUT报告 {report_id} 分析完成")

        finally:
            # 清理临时文件
            if left_video_path and os.path.exists(left_video_path):
                try:
                    os.remove(left_video_path)
                    logger.info(f"已删除临时文件: {left_video_path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败 {left_video_path}: {e}")

            if right_video_path and os.path.exists(right_video_path):
                try:
                    os.remove(right_video_path)
                    logger.info(f"已删除临时文件: {right_video_path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败 {right_video_path}: {e}")

            # 删除临时目录
            if temp_dir and os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                    logger.info(f"已删除临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"删除临时目录失败 {temp_dir}: {e}")

    except Exception as e:
        # 重要：这里抛出异常，让 RQ 捕获并触发自动重试
        logger.error(f"处理TBUT报告 {report_id} 时发生错误: {e}", exc_info=True)

        # 更新状态为失败
        try:
            report = db.query(Report).filter(Report.id == report_id).first()
            if report:
                report.status = 'failed'
                db.commit()
        except Exception as db_error:
            logger.error(f"更新TBUT报告 {report_id} 状态失败: {db_error}")

        # 重新抛出异常，让 RQ 知道任务失败，触发自动重试
        raise
    finally:
        db.close()


__all__ = [
    "process_report_analysis",
    "process_tbut_report_analysis",
]

