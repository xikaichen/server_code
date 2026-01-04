"""Shared AI analysis helpers and prompts."""

import json
from typing import List

import requests

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# 不同检查类型的图像分析提示词（用于左右眼单次分析）
CHECK_TYPE_GUIDE_PROMPTS = {
    2: "这是一张眼部图像，请估算泪河高度（Tear Meniscus Height），仅返回一个数值和单位，单位为毫米，不要附加任何解释。",
    3: "这是一张睑板腺成像图，请评估睑板腺腺体的缺失、堵塞和分泌情况，并用不超过30个字概括严重程度。",
    4: "这是一张用于评估泪膜破裂时间（FBUT）的眼部图像，请给出估算的破裂时间（单位：秒）并说明稳定性，整体回复控制在30个字以内。",
    5: "这是一张眼部图像，请评估眼红指数（0-100），仅返回数值以及简短的程度描述。",
    6: "这是一张睫毛显微图像，请判断是否存在螨虫感染，并给出感染程度及建议，字数不超过40个字。",
    7: "这是一张泪膜脂质层干涉图，请分析脂质层厚度与均匀性，并用不超过40个字概括泪膜稳定性。",
}

# 不同检查类型的专家分析提示词（用于得出专家分析）
CHECK_TYPE_EXPERT_PROMPTS = {
    2: "根据左右眼的泪河高度数据，给出泪液分泌情况的专业分析，并提供护理建议，只回复纯文本格式不用markdown格式",
    3: "根据左右眼的睑板腺分析结果，总结睑板腺健康状况并给出治疗或护理建议，只回复纯文本格式不用markdown格式",
    4: "结合左右眼的FBUT评估结果，分析泪膜稳定性并提供干眼管理建议，只回复纯文本格式不用markdown格式",
    5: "根据眼红指数结果，评估眼表充血程度并给出缓解建议，只回复纯文本格式不用markdown格式",
    6: "依据睫毛螨虫分析，判断感染风险并给出处理建议，只回复纯文本格式不用markdown格式",
    7: "根据脂质层分析结果，评估泪膜质量并提供护理建议，只回复纯文本格式不用markdown格式",
}


def get_ai_analysis(quest_messages: List[dict]) -> str:
    """
    调用AI服务进行眼部图像分析

    Args:
        quest_messages: AI提示消息

    Returns:
        str: AI分析结果
    """

    try:
        url = f"{settings.AIGC_API_URL}/v1/chat/completions"

        payload = json.dumps({
            "model": "gpt-5.1",
            "messages": quest_messages
        })

        headers = {
            'Authorization': settings.AIGC_API_KEY,
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        response_json = json.loads(response.text)
        logger.debug(f"AI分析响应: {response_json}")
        return response_json['choices'][0]['message']['content']
    except Exception as exc:  # pragma: no cover - logging helper
        logger.error(f"AI专家分析失败: {exc}", exc_info=True)
        raise Exception("专家分析失败") from exc


__all__ = [
    "CHECK_TYPE_GUIDE_PROMPTS",
    "CHECK_TYPE_EXPERT_PROMPTS",
    "get_ai_analysis",
]


