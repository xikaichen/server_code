from app.utils.database import Base
from sqlalchemy import Column, Integer, String, Date, DateTime, Text, Float
from sqlalchemy.sql import func

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, comment="患者姓名")
    gender = Column(Integer, comment="性别")
    birth = Column(Date, comment="出生年月")
    phone = Column(String(20), comment="联系电话")
    address = Column(String(200), comment="地址")
    medical_history = Column(Text, comment="病史")
    left_eye_power = Column(Float, comment="左眼度数")
    right_eye_power = Column(Float, comment="右眼度数")
    left_eye_astigmatism = Column(Float, comment="左眼散光")
    right_eye_astigmatism = Column(Float, comment="右眼散光")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间") 