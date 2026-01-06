from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from datetime import datetime, date
from app.models.patient import Patient
from app.models.report import Report
from app.models.questionnaire import Questionnaire
from app.models.response import Response
from app.models.user import UserResponse
from app.utils.database import get_db
from app.utils.security import get_current_user_dependency
from app.config import settings
from pydantic import BaseModel
from app.constants import error_codes
import logging

logger = logging.getLogger(__name__)

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
    created_by_user: int  # 创建患者的用户UID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


@patient_router.post("", response_model=Response[PatientResponse])
def create_patient(
    patient: PatientCreate,
    current_user: UserResponse = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """创建新患者（需要认证）

    自动设置 created_by_user 为当前登录用户的 UID
    """
    # 检查手机号是否已被当前用户使用
    if patient.phone:
        exists = (
            db.query(Patient)
            .filter(
                Patient.phone == patient.phone,
                Patient.created_by_user == current_user.uid
            )
            .first()
        )
        if exists:
            return Response(code=error_codes.CONFLICT, message="您已创建过使用此手机号的患者")

    # 创建患者记录，自动设置 created_by_user
    patient_data = patient.model_dump()
    patient_data['created_by_user'] = current_user.uid  # 服务端自动设置

    db_patient = Patient(**patient_data)
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)

    logger.info(f"用户 {current_user.uid} 创建了患者 ID={db_patient.id}")
    return Response(data=db_patient)


@patient_router.get("/{patient_id}", response_model=Response[PatientResponse])
def get_patient(
    patient_id: int,
    current_user: UserResponse = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """获取单个患者信息（需要认证，仅能查看自己创建的患者）"""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()

    if patient is None:
        return Response(code=error_codes.NOT_FOUND, message="患者未找到")

    # 权限检查：只能查看自己创建的患者
    if patient.created_by_user != current_user.uid:
        return Response(
            code=error_codes.FORBIDDEN,
            message="权限不足，只能查看自己创建的患者"
        )

    return Response(data=patient)


@patient_router.get("", response_model=Response[List[PatientResponse]])
def get_patient_list(
    keyword: Optional[str] = None,
    birth: Optional[str] = None,
    address: Optional[str] = None,
    gender: Optional[str] = None,
    page_no: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(5, ge=1, le=100, description="每页大小"),
    current_user: UserResponse = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """获取患者列表（需要认证，仅返回当前用户创建的患者）

    支持分页，搜索时返回所有结果
    """

    # 基础查询：只返回当前用户创建的患者
    list = db.query(Patient).filter(Patient.created_by_user == current_user.uid)
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
    current_user: UserResponse = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """更新患者信息（需要认证，仅能更新自己创建的患者）"""
    db_patient = db.query(Patient).filter(Patient.id == patient_id).first()

    if db_patient is None:
        return Response(code=error_codes.NOT_FOUND, message="患者未找到")

    # 权限检查：只能更新自己创建的患者
    if db_patient.created_by_user != current_user.uid:
        return Response(
            code=error_codes.FORBIDDEN,
            message="权限不足，只能更新自己创建的患者"
        )

    # 更新患者信息（不允许修改 created_by_user）
    for key, value in patient.model_dump(exclude_unset=True).items():
        if key != 'created_by_user':  # 防止客户端尝试修改创建者
            setattr(db_patient, key, value)

    db.commit()
    db.refresh(db_patient)

    logger.info(f"用户 {current_user.uid} 更新了患者 ID={patient_id}")
    return Response(data=db_patient)


@patient_router.delete("/{patient_id}", response_model=Response)
def delete_patient(
    patient_id: int,
    current_user: UserResponse = Depends(get_current_user_dependency),
    db: Session = Depends(get_db)
):
    """删除患者（需要认证，仅能删除自己创建的患者，级联删除关联的报告和问卷）"""
    try:
        # 查询患者是否存在
        db_patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if db_patient is None:
            return Response(code=error_codes.NOT_FOUND, message="患者未找到")

        # 权限检查：只能删除自己创建的患者
        if db_patient.created_by_user != current_user.uid:
            return Response(
                code=error_codes.FORBIDDEN,
                message="权限不足，只能删除自己创建的患者"
            )

        # 开始事务（使用 db.begin() 确保事务一致性）
        # 注意：SQLAlchemy Session 默认已经在事务中，但我们显式处理以确保原子性

        # 1. 首先删除关联的报告
        reports_deleted = db.query(Report).filter(Report.patient_id == patient_id).delete(synchronize_session=False)

        # 2. 删除关联的问卷
        questionnaires_deleted = db.query(Questionnaire).filter(Questionnaire.patient_id == patient_id).delete(synchronize_session=False)

        # 3. 最后删除患者记录
        db.delete(db_patient)

        # 提交事务
        db.commit()

        # 记录删除信息
        logger.info(f"用户 {current_user.uid} 成功删除患者 ID={patient_id}，同时删除了 {reports_deleted} 条报告和 {questionnaires_deleted} 条问卷")

        # 返回详细的删除信息
        message = f"患者删除成功"
        if reports_deleted > 0 or questionnaires_deleted > 0:
            message += f"（同时删除了 {reports_deleted} 条关联报告和 {questionnaires_deleted} 条关联问卷）"

        return Response(message=message)

    except SQLAlchemyError as e:
        # 发生错误时回滚事务
        db.rollback()
        logger.error(f"删除患者失败 ID={patient_id}: {str(e)}", exc_info=True)
        return Response(
            code=error_codes.INTERNAL_SERVER_ERROR,
            message=f"删除患者失败：数据库操作错误"
        )
    except Exception as e:
        # 处理其他未预期的错误
        db.rollback()
        logger.error(f"删除患者时发生未知错误 ID={patient_id}: {str(e)}", exc_info=True)
        return Response(
            code=error_codes.INTERNAL_SERVER_ERROR,
            message="删除患者失败：系统错误"
        )
