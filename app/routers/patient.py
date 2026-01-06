from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from app.models.patient import Patient
from app.models.response import Response
from app.models.user import UserResponse
from app.utils.database import get_db
from app.config import settings
from pydantic import BaseModel
from app.constants import error_codes

patient_router = APIRouter(prefix=f"{settings.API_V1_STR}/patient", tags=["patient"])


class PatientBase(BaseModel):
    name: str
    gender: Optional[int] = None
    birth: Optional[date] = None # 出生日期
    phone: Optional[str] = None
    address: Optional[str] = None
    medical_history: Optional[str] = None  # 病史
    left_eye_power: Optional[float] = None  # 左眼度数
    right_eye_power: Optional[float] = None  # 右眼度数
    left_eye_astigmatism: Optional[float] = None  # 左眼散光
    right_eye_astigmatism: Optional[float] = None  # 右眼散光


class PatientCreate(PatientBase):
    pass


class PatientUpdate(PatientBase):
    pass


class PatientResponse(PatientBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


@patient_router.post("", response_model=Response[PatientResponse])
def create_patient(
    patient: PatientCreate, 
    db: Session = Depends(get_db)
):
    """创建新患者"""
    if patient.phone:
        exists = (
            db.query(Patient)
            .filter(Patient.phone == patient.phone)
            .first()
        )
        if exists:
            return Response(code=error_codes.CONFLICT, message="手机号已存在")
    db_patient = Patient(**patient.model_dump())
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return Response(data=db_patient)


@patient_router.get("/{patient_id}", response_model=Response[PatientResponse])
def get_patient(
    patient_id: int, 
    db: Session = Depends(get_db)
):
    """获取单个患者信息"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        return Response(code=error_codes.NOT_FOUND, message="患者未找到")
    return Response(data=patient)


@patient_router.get("", response_model=Response[List[PatientResponse]])
def get_patient_list(
    keyword: Optional[str] = None,
    birth: Optional[str] = None,
    address: Optional[str] = None,
    gender: Optional[str] = None,
    page_no: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(5, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db)
):
    """获取患者列表（支持分页，搜索时返回所有结果）"""

    list = db.query(Patient)
    is_search = False  # 标记是否为搜索模式

    if keyword:
        # 通用搜索：根据ID、姓名或手机号搜索
        is_search = True
        try:
            # 尝试将搜索词转换为ID
            search_id = int(keyword)
            list = list.filter(Patient.id == search_id)
        except ValueError:
            # 如果不是数字，则按姓名或手机号搜索
            list = list.filter(
                (Patient.name.like(f"%{keyword}%")) |
                (Patient.phone.like(f"%{keyword}%"))
            )
    else:
        # 保持原有的单独搜索功能
        if gender:
            is_search = True
            list = list.filter(Patient.gender == int(gender))
        if birth:
            is_search = True
            list = list.filter(Patient.birth == birth)
        if address:
            is_search = True
            list = list.filter(Patient.address.like(f"%{address}%"))

    # 排序
    list = list.order_by(Patient.id.desc())

    # 如果是搜索模式，返回所有结果；否则应用分页
    if is_search:
        # 搜索模式：返回所有匹配结果
        list = list.all()
    else:
        # 普通加载模式：应用分页限制
        offset = (page_no - 1) * page_size
        list = list.offset(offset).limit(page_size).all()

    return Response(data=list)


@patient_router.put("/{patient_id}", response_model=Response[PatientResponse])
def update_patient(
    patient_id: int, 
    patient: PatientUpdate, 
    db: Session = Depends(get_db)
):
    """更新患者信息"""
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if db_patient is None:
        return Response(code=error_codes.NOT_FOUND, message="患者未找到")

    for key, value in patient.model_dump(exclude_unset=True).items():
        setattr(db_patient, key, value)

    db.commit()
    db.refresh(db_patient)
    return Response(data=db_patient)


@patient_router.delete("/{patient_id}", response_model=Response)
def delete_patient(
    patient_id: int, 
    db: Session = Depends(get_db)
):
    """删除患者"""
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if db_patient is None:
        return Response(code=error_codes.NOT_FOUND, message="患者未找到")

    db.delete(db_patient)
    db.commit()
    return Response(message="Patient deleted successfully")
