from app.utils.database import Base
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

class Report(Base):
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, comment="患者Id")
    check_type = Column(Integer, comment="检查类型")
    check_result = Column(String(3000), comment="检查结果")
    suggestion = Column(String(3000), comment="指导建议")
    expert_analyse = Column(Text, comment="专家分析")
    left_eye_image = Column(String(3000), comment="左眼图片Base64")
    right_eye_image = Column(String(3000), comment="右眼图片Base64")
    status = Column(String(20), default='processing', comment="处理状态: processing-处理中, completed-已完成, failed-失败")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="更新时间")