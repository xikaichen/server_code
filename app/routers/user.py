from datetime import timedelta, date
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from app.models.user import Token, UserResponse, UserDB
from app.models.response import Response
from app.constants.error_codes import (
    SUCCESS, BAD_REQUEST, UNAUTHORIZED, NOT_FOUND, 
    INTERNAL_SERVER_ERROR, TOO_MANY_REQUESTS, FORBIDDEN
)
from app.utils.security import (
    create_access_token, 
    ACCESS_TOKEN_EXPIRE_MINUTES, 
    get_current_user_with_blacklist_check_dependency,
    get_current_user_dependency,
    get_token_from_request,
    get_user_by_phone
)
from app.utils.database import get_redis_client, get_db
from app.config import settings
from app.utils.logging_config import get_logger
from sqlalchemy.orm import Session
import requests
import secrets
import time
import json
from typing import Optional
import random

logger = get_logger(__name__)

user_router = APIRouter(prefix=f"{settings.API_V1_STR}/user", tags=["user"])

# 获取Redis客户端
redis_client = get_redis_client()

# 配置信息
class Config:
    SMS_CODE_EXPIRE = 300  # 验证码有效期(秒)
    SMS_CODE_LENGTH = 6  # 验证码长度
    SMS_SEND_INTERVAL = 60  # 短信发送间隔(秒)
    MAX_ATTEMPTS = 5  # 最大尝试次数
    BLOCK_TIME = 600  # 锁定时间(秒)
    TOKEN_EXPIRE = 86400  # 令牌有效期(秒)

# 生成随机验证码
def generate_sms_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(Config.SMS_CODE_LENGTH))

# 生成唯一随机整型uid

def generate_unique_uid(db: Session, length: int = 8) -> int:
    """
    生成全库唯一的随机整型uid
    """
    while True:
        uid = random.randint(10**(length-1), 10**length-1)
        exists = db.query(UserDB).filter(UserDB.uid == uid).first()
        if not exists:
            return uid

class SMSCodeForm(BaseModel):
    phone: str

class VerifySMSCodeForm(BaseModel):
    phone: str
    code: str
    invite_code: str  # 邀请码字段

@user_router.post("/login/get_sms_code", response_model=Response)
async def get_sms_code(form_data: SMSCodeForm):
    """
    用户发送登录验证码接口
    """

    phone = form_data.phone

    # 检查是否在发送间隔内
    stored_data = redis_client.get(f"sms_code:{phone}")
    if stored_data:
        stored_data = json.loads(stored_data)
        last_send_time = stored_data.get("send_time", 0)
        current_time = time.time()
        if current_time - last_send_time < Config.SMS_SEND_INTERVAL:
            remaining_time = int(Config.SMS_SEND_INTERVAL - (current_time - last_send_time))
            return Response(
                code=TOO_MANY_REQUESTS,
                message=f"验证码发送过于频繁，请等待 {remaining_time} 秒后重试"
            )

    # 生成验证码
    code = generate_sms_code()
    
    # 存储验证码和过期时间
    code_data = {
        "code": code,
        "expire_time": time.time() + Config.SMS_CODE_EXPIRE,
        "send_time": time.time()
    }
    
    # 将验证码数据存储到Redis，并设置过期时间
    redis_client.setex(
        f"sms_code:{phone}",
        Config.SMS_CODE_EXPIRE,
        json.dumps(code_data)
    )

    logger.debug(f"发送验证码到手机号: {phone}")

    # 发送验证码
    body = {"name": settings.SMS_PLATFORM_NAME, "code": code, "targets": phone}
    requests.post(settings.SMS_PLATFORM_URL, json=body)

    return Response(
        code=SUCCESS,
        message="验证码发送成功"
    )

@user_router.post("/login", response_model=Response[dict])
async def login(form_data: VerifySMSCodeForm, db: Session = Depends(get_db)):
    """
    验证验证码并登录
    """
    phone = form_data.phone
    code = form_data.code
    invite_code = form_data.invite_code

    # 验证邀请码
    if not invite_code or invite_code.strip() == "":
        return Response(
            code=BAD_REQUEST,
            message="邀请码不能为空"
        )
    
    # 检查邀请码是否有效
    if invite_code.strip() not in settings.INVITE_CODES:
        return Response(
            code=BAD_REQUEST,
            message="邀请码无效，请输入正确的邀请码"
        )

    # 从Redis获取验证码数据
    stored_data = redis_client.get(f"sms_code:{phone}")
    if not stored_data:
        return Response(
            code=BAD_REQUEST,
            message="验证码不存在，请重新获取验证码"
        )

    stored_code_data = json.loads(stored_data)
    
    # 检查验证码是否过期
    if time.time() > stored_code_data["expire_time"]:
        redis_client.delete(f"sms_code:{phone}")  # 删除过期的验证码
        return Response(
            code=BAD_REQUEST,
            message="验证码已过期，请重新获取验证码"
        )

    # 验证码是否正确
    if code != stored_code_data["code"]:
        return Response(
            code=BAD_REQUEST,
            message="验证码错误"
        )

    # 验证成功后删除验证码
    redis_client.delete(f"sms_code:{phone}")

    # 从数据库获取或创建用户
    user = get_user_by_phone(db, phone)
    if not user:
        # 创建新用户
        user = UserDB(
            phone=phone,
            uid=generate_unique_uid(db)
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 生成访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": phone},
        expires_delta=access_token_expires,
    )

    # 构建用户信息
    user_info = UserResponse(
        uid=user.uid,
        phone=user.phone,
        name=user.name,
        address=user.address,
        birth=user.birth,
        gender=user.gender,
        created_at=user.created_at.isoformat() if user.created_at else None,
        updated_at=user.updated_at.isoformat() if user.updated_at else None
    )

    return Response(
        code=SUCCESS,
        message="登录成功",
        data={
            "access_token": access_token, 
            "token_type": "bearer",
            "user": user_info
        }
    )

@user_router.post("/logout", response_model=Response)
async def logout(request: Request):
    """
    用户登出接口
    """
    try:
        # 从请求头中获取token
        token = get_token_from_request(request)
        
        # 将token加入黑名单，过期时间与token有效期一致
        redis_client.setex(
            f"token_blacklist:{token}",
            ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 转换为秒
            "blacklisted"
        )
        
        return Response(
            code=SUCCESS,
            message="登出成功"
        )
    except Exception as e:
        logger.error(f"用户登出失败: {e}", exc_info=True)
        return Response(
            code=INTERNAL_SERVER_ERROR,
            message=f"登出失败: {str(e)}"
        )

class UpdateUserForm(BaseModel):
    """
    用户信息更新表单（不允许编辑手机号 phone 字段）
    """
    uid: Optional[int] = None
    name: Optional[str] = None
    address: Optional[str] = None
    birth: Optional[date] = None
    gender: Optional[int] = None  # 性别字段 1-男 0-女

@user_router.put("/info", response_model=Response[UserResponse])
async def update_user_info(
    form_data: UpdateUserForm,
    current_user: UserResponse = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    更新用户信息接口
    客户端传递uid和要更新的信息（不允许编辑手机号 phone 字段）
    """
    try:
        # 如果没传uid则用当前用户的uid
        uid = form_data.uid if form_data.uid else current_user.uid
        # 获取要更新的用户（通过uid）
        user = db.query(UserDB).filter(UserDB.uid == uid).first()
        if not user:
            return Response(
                code=NOT_FOUND,
                message="用户不存在"
            )
        # 权限检查：用户只能更新自己的信息
        if current_user.uid != user.uid:
            return Response(
                code=FORBIDDEN,
                message="权限不足，只能更新自己的信息"
            )
        # 更新用户信息
        if form_data.name is not None:
            user.name = form_data.name
        if form_data.address is not None:
            user.address = form_data.address
        if form_data.birth is not None:
            user.birth = form_data.birth
        if form_data.gender is not None:
            user.gender = form_data.gender
        db.commit()
        db.refresh(user)
        # 返回更新后的用户信息
        updated_user = UserResponse(
            uid=user.uid,
            name=user.name,
            phone=user.phone,
            address=user.address,
            birth=user.birth,
            gender=user.gender,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None
        )
        return Response(
            code=SUCCESS,
            message="用户信息更新成功",
            data=updated_user
        )
    except Exception as e:
        logger.error(f"更新用户信息失败: {e}", exc_info=True)
        return Response(
            code=INTERNAL_SERVER_ERROR,
            message=f"更新用户信息失败: {str(e)}"
        )

@user_router.get("/info", response_model=Response[UserResponse])
async def get_user_info(
    current_user: UserResponse = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """
    获取用户信息接口
    """
    try:
        # 用current_user.uid查数据库
        user = db.query(UserDB).filter(UserDB.uid == current_user.uid).first()
        if not user:
            return Response(
                code=NOT_FOUND,
                message="用户不存在"
            )
        user_info = UserResponse(
            uid=user.uid,
            phone=user.phone,
            name=user.name,
            address=user.address,
            birth=user.birth,
            gender=user.gender,
            created_at=user.created_at.isoformat() if user.created_at else None,
            updated_at=user.updated_at.isoformat() if user.updated_at else None
        )
        return Response(
            code=SUCCESS,
            message="获取用户信息成功",
            data=user_info
        )
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}", exc_info=True)
        return Response(
            code=INTERNAL_SERVER_ERROR,
            message=f"获取用户信息失败: {str(e)}"
        )