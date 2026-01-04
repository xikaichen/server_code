from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.user import UserResponse, UserDB
from app.config import settings
from app.utils.database import get_redis_client, get_db
from sqlalchemy.orm import Session

# 配置密钥和算法
SECRET_KEY = "your-secret-key-here"  # 在生产环境中应该使用环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200  # 43200 为 1个月 (30天 * 24小时 * 60分钟)

# 创建HTTPBearer实例
security = HTTPBearer()

# 获取Redis客户端
redis_client = get_redis_client()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """解码令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def is_token_blacklisted(token: str, redis_client) -> bool:
    """检查token是否在黑名单中"""
    try:
        # 使用token的哈希作为key来检查黑名单
        blacklisted = redis_client.get(f"token_blacklist:{token}")
        return blacklisted is not None
    except Exception:
        return False

def get_user_by_phone(db: Session, phone: str) -> Optional[UserDB]:
    """根据手机号从数据库获取用户"""
    return db.query(UserDB).filter(UserDB.phone == phone).first()

def create_user_from_token(payload: dict, db: Session) -> UserResponse:
    """从token payload创建用户对象"""
    phone: str = payload.get("sub")
    if phone is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 从数据库获取用户信息
    user_db = get_user_by_phone(db, phone)
    if not user_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建用户响应对象
    user = UserResponse(
        uid=user_db.uid,
        phone=user_db.phone,
        name=user_db.name,
        address=user_db.address,
        created_at=user_db.created_at.isoformat() if user_db.created_at else None,
        updated_at=user_db.updated_at.isoformat() if user_db.updated_at else None
    )
    
    return user

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> UserResponse:
    """获取当前用户（基础版本，不检查黑名单）"""
    token = credentials.credentials
    
    # 解码token
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return create_user_from_token(payload, db)

def get_token_from_request(request: Request) -> str:
    """从请求中获取token"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return auth_header.split(" ")[1]

async def get_current_user_with_blacklist_check(request: Request, redis_client, db: Session) -> UserResponse:
    """获取当前用户并检查黑名单"""
    token = get_token_from_request(request)
    
    # 检查token是否在黑名单中
    if is_token_blacklisted(token, redis_client):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 解码token
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return create_user_from_token(payload, db)

# 统一的认证依赖函数，用于中间件
async def get_current_user_with_blacklist_check_dependency(request: Request, db: Session) -> UserResponse:
    """统一的认证依赖函数，包含黑名单检查"""
    return await get_current_user_with_blacklist_check(request, redis_client, db) 

# 用于路由的依赖函数
async def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security), 
    db: Session = Depends(get_db)
) -> UserResponse:
    """用于路由的当前用户依赖函数"""
    token = credentials.credentials
    
    # 检查token是否在黑名单中
    if is_token_blacklisted(token, redis_client):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 解码token
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return create_user_from_token(payload, db) 