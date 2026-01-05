import os
import base64
import datetime
import random
import string
from pathlib import Path
from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel
from typing import Optional
from qiniu import Auth, put_data
from app.config import settings
from app.models.response import Response
from app.constants import error_codes
from app.utils.logging_config import get_logger
import hashlib

logger = get_logger(__name__)

upload_router = APIRouter(prefix=f"{settings.API_V1_STR}/upload", tags=["upload"])

# 七牛云配置（请替换为你的实际配置）
access_key = "gqsJdMzTPYcozaTz9ivoVX9Vv2MG8oL22XgOW5Rl"
secret_key = "1kCS0uLpKwrIbY4ZHHxukxRmp2teUw8N8KGQSnIi"
bucket_name = "yuekai-ophthalmology"
domain = "https://cdn.yokai-tech.com"

# 本地存储配置
UPLOAD_DIR = Path(__file__).parent.parent.parent / 'uploads'
UPLOAD_DIR.mkdir(exist_ok=True)

class Base64UploadRequest(BaseModel):
    base64_data: str
    filename: Optional[str] = None

# 生成七牛 key
def generate_qiniu_key(filename: str) -> str:
    """生成七牛云存储的唯一key"""
    now = datetime.datetime.now()
    date_path = now.strftime("%Y/%m/%d")
    millis = int(now.timestamp() * 1000)
    rand_str = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    name, ext = os.path.splitext(filename)
    ext = ext or ".jpg"
    first_char = name[0] if name else "x"
    return f"{date_path}/{millis}_{rand_str}_{first_char}{ext}"

# 生成本地文件名
def generate_local_filename() -> str:
    """生成本地存储的唯一文件名（使用随机哈希）"""
    # 直接生成随机哈希
    random_bytes = os.urandom(16)
    file_hash = hashlib.md5(random_bytes).hexdigest()[:16]

    return f"{file_hash}.mp4"

@upload_router.post("/base64")
async def upload_base64(data: Base64UploadRequest):
    logger.info(f"开始图片上传")
    try:
        base64_data = data.base64_data
        filename = data.filename
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]
        file_bytes = base64.b64decode(base64_data)
        orig_filename = filename or "upload.jpg"
        # 生成七牛 key
        qiniu_key = generate_qiniu_key(orig_filename)
        # 获取上传凭证
        q = Auth(access_key, secret_key)
        token = q.upload_token(bucket_name, qiniu_key, 3600)
        # 上传到七牛
        ret, info = put_data(token, qiniu_key, file_bytes)
        if info.status_code == 200:
            file_url = f"{domain}/{ret['key']}"
            return Response(code=error_codes.SUCCESS, message="上传成功", data={"url": file_url})
        else:
            return Response(code=error_codes.INTERNAL_SERVER_ERROR, message="上传到七牛失败")
    except Exception as e:
        logger.error(f"Base64上传异常: {e}", exc_info=True)
        return Response(code=error_codes.INTERNAL_SERVER_ERROR, message=f"上传异常: {str(e)}")

# @upload_router.post("/file")
# async def upload_file(file: UploadFile = File(...)):
#     """文件上传接口（用于视频等大文件）- 上传到七牛云"""
#     logger.info(f"开始video上传")
#     try:
#         # 读取文件内容
#         file_bytes = await file.read()
#         # 获取原始文件名
#         orig_filename = file.filename or "upload"
#         # 生成七牛 key
#         qiniu_key = generate_qiniu_key(orig_filename)
#         # 获取上传凭证
#         q = Auth(access_key, secret_key)
#         token = q.upload_token(bucket_name, qiniu_key, 3600)
#         # 上传到七牛
#         ret, info = put_data(token, qiniu_key, file_bytes)
#         if info.status_code == 200:
#             file_url = f"{domain}/{ret['key']}"
#             return Response(code=error_codes.SUCCESS, message="上传成功", data={"url": file_url})
#         else:
#             return Response(code=error_codes.INTERNAL_SERVER_ERROR, message="上传到七牛失败")
#     except Exception as e:
#         logger.error(f"文件上传异常: {e}", exc_info=True)
#         return Response(code=error_codes.INTERNAL_SERVER_ERROR, message=f"上传异常: {str(e)}")

# ==================== 本地存储接口 ====================

@upload_router.post("/file")
async def upload_file(file: UploadFile = File(...)):
    """文件上传接口（保存到本地临时目录）- 用于视频等大文件"""
    logger.info(f"开始本地文件上传")
    try:
        # 读取文件内容
        file_bytes = await file.read()

        # 生成随机文件名
        filename = generate_local_filename()
        file_path = UPLOAD_DIR / filename

        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存文件到本地
        with open(file_path, 'wb') as f:
            f.write(file_bytes)

        # 返回文件访问URL
        file_url = f"{UPLOAD_DIR}/{filename}"

        logger.info(f"文件上传成功: {file_path}")
        return Response(code=error_codes.SUCCESS, message="上传成功", data={"url": file_url})

    except Exception as e:
        logger.error(f"本地文件上传异常: {e}", exc_info=True)
        return Response(code=error_codes.INTERNAL_SERVER_ERROR, message=f"上传异常: {str(e)}")
