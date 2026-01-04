from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from app.config import settings
from typing import Optional
from app.models.response import Response
from app.models.user import UserResponse
from sqlalchemy.orm import Session
from app.utils.database import get_db
from app.models.report import Report
from app.models.patient import Patient
from app.constants import error_codes
from typing import List
from app.utils.tasks import enqueue_report_analysis, enqueue_tbut_report_analysis
from app.services.ai_analysis import (
    CHECK_TYPE_GUIDE_PROMPTS,
    CHECK_TYPE_EXPERT_PROMPTS,
)
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

report_router = APIRouter(prefix=f"{settings.API_V1_STR}/report", tags=["report"])

# 新增递归截断 base64 工具函数
def safe_truncate_base64(obj, max_len=40):
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if k == 'image_url' and isinstance(v, dict) and 'url' in v:
                # 截断 base64 字段
                url = v['url']
                if isinstance(url, str) and len(url) > max_len:
                    new_obj[k] = v.copy()
                    new_obj[k]['url'] = url[:max_len] + '...'
                else:
                    new_obj[k] = v
            else:
                new_obj[k] = safe_truncate_base64(v, max_len)
        return new_obj
    elif isinstance(obj, list):
        return [safe_truncate_base64(item, max_len) for item in obj]
    else:
        return obj

class ReportCreate(BaseModel):
    patient_id: int   # 患者Id
    check_type: int  # 检查类型
    check_result: str = ""  # 检查结果
    left_eye_image: str  # 左眼图片Base64
    right_eye_image: str  # 右眼图片Base64
    suggestion: str = ""  # 指导建议
    expert_analyse: str = ""  # 专家分析

class ReportCreateResponse(BaseModel):
    id: int
    status: str  # 处理状态: processing-处理中, completed-已完成, failed-失败

class ReportDetailResponse(BaseModel):
    id: int
    patient_id: int
    check_type: int
    check_result: str
    left_eye_image: str
    right_eye_image: str
    suggestion: str
    expert_analyse: str
    status: str  # 处理状态: processing-处理中, completed-已完成, failed-失败
    created_at: datetime
    updated_at: Optional[datetime] = None

class ReportListResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_phone: str
    patient_gender: int
    patient_birth: date
    patient_address: str
    suggestion: str
    expert_analyse: str
    check_type: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

class PaginatedReportListResponse(BaseModel):
    """分页报告列表响应"""
    list: List[ReportListResponse]
    total: int  # 总记录数

class ReportEdit(BaseModel):
    left_eye_image: Optional[str] = None
    right_eye_image: Optional[str] = None
    suggestion: Optional[str] = None
    expert_analyse: Optional[str] = None

@report_router.post("", response_model=Response[ReportCreateResponse])
def create_report(
    report: ReportCreate, 
    db: Session = Depends(get_db)
):
    """创建新报告（异步处理AI分析）"""
    try:
        # 定义不需要AI分析的检查类型
        # 1: 眼表拍照（常规检查）
        # 7: 脂质层分析（视频，不需要AI分析）
        no_ai_analysis_types = {1, 7}

        # 验证检查类型
        # check_type == 4 (FBUT) 使用专门的处理逻辑，不需要验证提示词
        if report.check_type not in no_ai_analysis_types and report.check_type != 4:
            guide_prompt = CHECK_TYPE_GUIDE_PROMPTS.get(report.check_type)
            if not guide_prompt:
                return Response(code=error_codes.BAD_REQUEST, message="不支持的检查类型")

        # 创建报告记录
        # 不需要AI分析的类型直接设为completed，其他类型设为processing等待AI分析
        report_data = report.model_dump()
        report_data['status'] = 'completed' if report.check_type in no_ai_analysis_types else 'processing'

        db_report = Report(**report_data)
        db.add(db_report)
        db.commit()
        db.refresh(db_report)

        # 根据检查类型提交不同的异步任务
        if report.check_type == 4:
            # FBUT泪膜破裂时间使用专门的任务处理
            enqueue_tbut_report_analysis(db_report.id)
        elif report.check_type not in no_ai_analysis_types:
            # 其他需要AI分析的检查类型使用通用任务处理
            enqueue_report_analysis(db_report.id)

        return Response(data=ReportCreateResponse(
            id=db_report.id,
            status=db_report.status
        ))
    except Exception as e:
        logger.error(f"创建报告失败: {e}", exc_info=True)
        return Response(code=error_codes.INTERNAL_SERVER_ERROR, message="创建报告失败")

@report_router.get("/{report_id}", response_model=Response[ReportDetailResponse])
def get_report_detail(
    report_id: int, 
    db: Session = Depends(get_db)
):
    """获取单个报告"""

    report = db.query(Report).filter(Report.id == report_id).first()

    if report is None:
        return Response(code=error_codes.NOT_FOUND, message="报告未找到")

    return Response(data=report)

@report_router.get("/{report_id}/status", response_model=Response[dict])
def get_report_status(
    report_id: int, 
    db: Session = Depends(get_db)
):
    """获取报告处理状态"""
    report = db.query(Report).filter(Report.id == report_id).first()

    if report is None:
        return Response(code=error_codes.NOT_FOUND, message="报告未找到")

    return Response(data={
        "id": report.id,
        "status": report.status or "processing"
    })

@report_router.get("", response_model=Response[PaginatedReportListResponse])
def get_report_list(
    keyword: Optional[str] = None,
    birth: Optional[str] = None,
    address: Optional[str] = None,
    gender: Optional[str] = None,
    patient_id: int = 0,
    page_no: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db),
):
    """获取报告列表（支持分页）"""  
    
    list = db.query(Report)

    # 如果是获取指定患者报告，则只获取该患者报告
    if patient_id != 0:
        list = list.filter(Report.patient_id == patient_id)

    # 如果是获取所有报告，则根据关键词、性别、出生日期、地址搜索
    elif keyword:
        # 通用搜索：根据ID、姓名或手机号搜索
        try:
            # 尝试将搜索词转换为ID
            search_id = int(keyword)
            list = list.filter(Report.patient_id == search_id)
        except ValueError:
            # 如果不是数字，则按姓名或手机号搜索
            list = list.join(Patient, Report.patient_id == Patient.id).filter(
                (Patient.name.like(f"%{keyword}%")) |
                (Patient.phone.like(f"%{keyword}%"))
            )
    else:
        # 保持原有的单独搜索功能
        has_patient_filter = any([gender, birth, address])
        if has_patient_filter:
            list = list.join(Patient, Report.patient_id == Patient.id)
        if gender:
            list = list.filter(Patient.gender == int(gender))
        if birth:
            list = list.filter(Patient.birth == birth)
        if address:
            list = list.filter(Patient.address.like(f"%{address}%"))
    
    # 计算总记录数（在分页前）
    total = list.count()
    
    # 分页查询
    offset = (page_no - 1) * page_size
    list = list.order_by(Report.id.desc()).offset(offset).limit(page_size).all()

    result = []
    for report in list:
        patient = db.query(Patient).filter(Patient.id == report.patient_id).first()
        if not patient:
            continue
        result.append(ReportListResponse(
            id=report.id,
            patient_id=report.patient_id,
            patient_name=patient.name,
            patient_phone=patient.phone,
            patient_gender=patient.gender,
            patient_birth=patient.birth,
            patient_address=patient.address,
            suggestion=report.suggestion,
            expert_analyse=report.expert_analyse,
            check_type=report.check_type,
            status=report.status or "processing",
            created_at=report.created_at,
            updated_at=report.updated_at,
        ))
    
    # 返回分页响应
    paginated_response = PaginatedReportListResponse(
        list=result,
        total=total,
    )

    return Response(data=paginated_response)

@report_router.put("/{report_id}", response_model=Response[ReportDetailResponse])
def edit_report(
    report_id: int,
    report_update: ReportEdit,
    db: Session = Depends(get_db),
):
    """编辑报告"""
    db_report = db.query(Report).filter(Report.id == report_id).first()
    if db_report is None:
        return Response(code=error_codes.NOT_FOUND, message="报告未找到")

    update_data = report_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_report, key, value)
    db.commit()
    db.refresh(db_report)
    return Response(data=db_report)