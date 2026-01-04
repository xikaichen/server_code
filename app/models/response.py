from pydantic import BaseModel
from typing import TypeVar, Generic, Optional

T = TypeVar('T')

class Response(BaseModel, Generic[T]):
    """通用响应模型"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None 