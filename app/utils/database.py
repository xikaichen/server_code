from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import redis

from app.config import settings

# 创建数据库引擎
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

# 获取数据库会话的依赖函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_redis_client():
    """
    获取Redis客户端实例（用于常规操作，自动解码响应为字符串）
    
    适用于：
    - 存储/读取JSON字符串（如SMS验证码、token黑名单等）
    - 需要直接使用字符串的场景
    """
    redis_config = {
        'host': settings.REDIS_HOST,
        'port': settings.REDIS_PORT,
        'db': settings.REDIS_DB,
        'decode_responses': True  # 自动解码为字符串，方便使用
    }

    # 只有在设置了密码时才添加password参数
    if settings.REDIS_PASSWORD:
        redis_config['password'] = settings.REDIS_PASSWORD

    return redis.Redis(**redis_config)

def get_redis_client_for_rq():
    """
    获取Redis客户端实例（用于RQ，不自动解码响应，支持二进制数据）
    
    适用于：
    - RQ任务队列（使用pickle序列化，数据是二进制格式）
    - 需要处理二进制数据的场景
    
    注意：RQ使用pickle序列化任务参数，如果decode_responses=True会导致UnicodeDecodeError
    """
    redis_config = {
        'host': settings.REDIS_HOST,
        'port': settings.REDIS_PORT,
        'db': settings.REDIS_DB,
        'decode_responses': False  # RQ需要处理二进制数据，不能自动解码
    }

    # 只有在设置了密码时才添加password参数
    if settings.REDIS_PASSWORD:
        redis_config['password'] = settings.REDIS_PASSWORD

    return redis.Redis(**redis_config) 