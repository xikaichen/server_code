from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.config import settings
from typing import Optional
from app.models.response import Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.utils.database import get_db
from app.models.questionnaire import Questionnaire
from app.constants import error_codes
from typing import List
from app.models.patient import Patient
import logging

logger = logging.getLogger(__name__)

questionnaire_router = APIRouter(prefix=f"{settings.API_V1_STR}/questionnaire", tags=["questionnaire"])

class QuestionnaireCreate(BaseModel):
    answer: str  # 答案
    patient_id: int

class QuestionnaireCreateResponse(BaseModel):
    id: int

class QuestionnaireListResponse(BaseModel):
    id: int
    answer: str
    patient_id: int
    patient_name: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class QuestionnaireDetailResponse(BaseModel):
    id: int
    answer: str
    patient_id: int
    patient_name: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

@questionnaire_router.post("", response_model=Response[QuestionnaireCreateResponse])
def create_questionnaire(
    questionnaire: QuestionnaireCreate, 
    db: Session = Depends(get_db)
):
    """创建问卷"""
    db_questionnaire = Questionnaire(**questionnaire.model_dump())
    db.add(db_questionnaire)
    db.commit()
    db.refresh(db_questionnaire)
    return Response(data=db_questionnaire)

@questionnaire_router.get("", response_model=Response[List[QuestionnaireListResponse]])
def get_questionnaire_list(
    patient_id: int = 0, 
    db: Session = Depends(get_db)
):
    """获取问卷列表"""

    query = db.query(Questionnaire).order_by(Questionnaire.id.desc())
    
    if patient_id != 0:
        query = query.filter(Questionnaire.patient_id == patient_id)
    
    questionnaire_list = query.all()

    for questionnaire in questionnaire_list:
        patient = db.query(Patient).filter(Patient.id == questionnaire.patient_id).first()
        questionnaire.patient_name = patient.name

    return Response(data=questionnaire_list)

@questionnaire_router.get("/{questionnaire_id}", response_model=Response[QuestionnaireDetailResponse])
def get_questionnaire_detail(
    questionnaire_id: int,
    db: Session = Depends(get_db)
):
    """获取问卷详情"""

    questionnaire = db.query(Questionnaire).filter(Questionnaire.id == questionnaire_id).first()
    if questionnaire is None:
        return Response(code=error_codes.NOT_FOUND, message="问卷未找到")

    patient = db.query(Patient).filter(Patient.id == questionnaire.patient_id).first()

    questionnaire_detail = QuestionnaireDetailResponse(
        id=questionnaire.id,
        answer=questionnaire.answer,
        patient_id=questionnaire.patient_id,
        patient_name=patient.name if patient else "",
        created_at=questionnaire.created_at,
        updated_at=questionnaire.updated_at
    )

    return Response(data=questionnaire_detail)

@questionnaire_router.delete("/{questionnaire_id}", response_model=Response)
def delete_questionnaire(
    questionnaire_id: int,
    db: Session = Depends(get_db)
):
    """删除问卷（级联删除关联的响应记录）

    注意：当前数据库架构中，问卷答案直接存储在questionnaire表的answer字段中（JSON格式），
    没有单独的response表。此实现为未来可能的架构扩展预留了级联删除的结构。
    如果将来添加了独立的response表（包含questionnaire_id外键），
    可以在此处添加级联删除逻辑。
    """
    try:
        # 查询问卷是否存在
        db_questionnaire = db.query(Questionnaire).filter(Questionnaire.id == questionnaire_id).first()
        if db_questionnaire is None:
            return Response(code=error_codes.NOT_FOUND, message="问卷未找到")

        # 开始事务（使用 db.begin() 确保事务一致性）
        # 注意：SQLAlchemy Session 默认已经在事务中，但我们显式处理以确保原子性

        # 未来扩展点：如果有独立的response表，在此处添加级联删除
        # 示例代码（当前注释掉，因为response表不存在）：
        # responses_deleted = db.query(QuestionnaireResponse).filter(
        #     QuestionnaireResponse.questionnaire_id == questionnaire_id
        # ).delete(synchronize_session=False)

        responses_deleted = 0  # 当前架构下没有独立的response记录

        # 删除问卷记录
        db.delete(db_questionnaire)

        # 提交事务
        db.commit()

        # 记录删除信息
        logger.info(f"成功删除问卷 ID={questionnaire_id}，同时删除了 {responses_deleted} 条响应记录")

        # 返回详细的删除信息
        message = f"问卷删除成功"
        if responses_deleted > 0:
            message += f"（同时删除了 {responses_deleted} 条关联响应记录）"

        return Response(message=message)

    except SQLAlchemyError as e:
        # 发生错误时回滚事务
        db.rollback()
        logger.error(f"删除问卷失败 ID={questionnaire_id}: {str(e)}", exc_info=True)
        return Response(
            code=error_codes.INTERNAL_SERVER_ERROR,
            message=f"删除问卷失败：数据库操作错误"
        )
    except Exception as e:
        # 处理其他未预期的错误
        db.rollback()
        logger.error(f"删除问卷时发生未知错误 ID={questionnaire_id}: {str(e)}", exc_info=True)
        return Response(
            code=error_codes.INTERNAL_SERVER_ERROR,
            message="删除问卷失败：系统错误"
        )