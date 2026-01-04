from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.response import Response
from app.utils.database import Base
from sqlalchemy import Column, Integer, String, DateTime, Date
from sqlalchemy.sql import func
from datetime import date
import uuid

class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: int
    email: EmailStr
    phone: str  # 手机号
    password: str
    is_active: bool = True

class UserResponse(BaseModel):
    uid: int
    name: Optional[str] = None
    phone: str
    address: Optional[str] = None
    birth: Optional[date] = None
    gender: Optional[int] = None  # 性别字段 1-男 0-女
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class UserInDB(BaseModel):
    id: int
    email: Optional[str] = None
    phone: str
    password: str
    is_active: bool = True
    birth: Optional[date] = None

# SQLAlchemy 数据库模型
class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    uid = Column(Integer, unique=True, nullable=False, index=True, comment="对外唯一用户ID")
    name = Column(String(100), nullable=True, comment="姓名")
    phone = Column(String(20), unique=True, nullable=False, comment="手机号")
    address = Column(String(255), nullable=True, comment="地址")
    birth = Column(Date, nullable=True, comment="生日")
    gender = Column(Integer, nullable=True, comment="性别 1-男 0-女")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")