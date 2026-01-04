from app.utils.database import Base
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

class Questionnaire(Base):
    __tablename__ = 'questionnaires'

    id = Column(Integer, primary_key=True, index=True)
    answer = Column(String(3000), comment="答案")
    patient_id = Column(Integer, comment="患者ID")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")