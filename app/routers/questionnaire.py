from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.config import settings
from typing import Optional
from app.models.response import Response
from sqlalchemy.orm import Session
from app.utils.database import get_db
from app.models.questionnaire import Questionnaire
from app.constants import error_codes
from typing import List
from app.models.patient import Patient

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