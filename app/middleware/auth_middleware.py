from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Optional, Callable
from app.utils.security import get_current_user_with_blacklist_check_dependency
from app.utils.database import get_db

def create_auth_middleware(app, protected_paths: Optional[List[str]] = None):
    """
    创建 FastAPI 认证中间件
    
    Args:
        app: FastAPI应用实例
        protected_paths: 需要认证保护的路由路径列表，如果为None则使用默认保护路径
    """
    # 定义需要认证的路径模式，支持模糊匹配
    auth_patterns = [
        "/api/v1/patient",
        "/api/v1/questionnaire",
        "/api/v1/user/logout",
        "/api/v1/report",  # 报告相关接口
    ]
    
    # 定义不需要认证的路径模式，支持模糊匹配
    public_patterns = [
        "/api/v1/report/",  # 获取单个报告详情
        "/api/v1/patient/",  # 获取单个患者详情
    ]
    
    protected_paths = protected_paths or auth_patterns
    
    def _is_protected_path(path: str) -> bool:
        print('path', path)
        """检查路径是否需要认证"""
        # 先检查是否匹配公开路径模式
        for pattern in public_patterns:
            if path.startswith(pattern):
                return False
        
        # 再检查是否匹配需要认证的路径
        return any(path.startswith(protected_path) for protected_path in protected_paths)
    
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next: Callable):
        """中间件处理逻辑"""
        
        # 检查路径是否需要认证
        if _is_protected_path(request.url.path):
            try:
                # 手动获取 Session
                db_gen = get_db()
                db = next(db_gen)
                try:
                    await get_current_user_with_blacklist_check_dependency(request, db)
                finally:
                    db_gen.close()
            except HTTPException as e:
                # 认证失败，返回错误响应
                return JSONResponse(
                    status_code=e.status_code,
                    content={
                        "code": e.status_code,
                        "message": e.detail,
                        "data": None
                    }
                )
        
        # 继续处理请求
        response = await call_next(request)
        return response
    
    return auth_middleware 