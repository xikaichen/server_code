from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, StarletteHTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from app.routers.user import user_router
from app.routers.patient import patient_router
from app.routers.report import report_router
from app.routers.questionnaire import questionnaire_router
from app.routers.upload import upload_router
from app.models.user import Response
from app.middleware.auth_middleware import create_auth_middleware
from app.utils.logging_config import setup_logging, get_logger
from app.config import settings
import redis
import logging

# 初始化日志系统
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="yuekai_ophthalmology",
    description="666",
    version="1.0.0",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加认证中间件
create_auth_middleware(app)

# 全局处理 Redis 异常
@app.exception_handler(redis.exceptions.RedisError)
async def redis_exception_handler(request: Request, exc: redis.exceptions.RedisError):
    logger.error(f"Redis异常: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": f"Redis 服务异常", "data": None}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    logger.warning(f"HTTP异常 [{exc.status_code}]: {exc.detail}")

    # return PlainTextResponse(str(exc.detail), status_code=exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content=Response(
            code=exc.status_code,
            message=str(exc.detail),
            data=None
        ).model_dump()
    )
    # return Response(code=exc.status_code, message=str(exc.detail)).model_dump()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    处理请求参数验证错误
    当请求参数不符合预期格式时，FastAPI 会抛出 RequestValidationError 异常
    此处理器会捕获这些异常并返回统一的错误响应格式

    Args:
        request (Request): 原始请求对象
        exc (RequestValidationError): 验证错误异常对象，包含详细的错误信息

    Returns:
        JSONResponse: 包含以下字段的 JSON 响应：
            - code: 422 表示参数验证错误
            - message: 错误信息，包含所有验证失败的原因
            - data: null
    """

    error_messages = [f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()]

    logger.warning(f"请求参数验证失败: {error_messages}")

    return JSONResponse(
        status_code=422,
        content=Response(
            code=422,
            message=", ".join(error_messages),
            data=None
        ).model_dump()
    )

# 应用启动事件
@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI 应用启动成功")
    logger.info(f"应用名称: {app.title}")
    logger.info(f"版本: {app.version}")
    logger.info(f"调试模式: {settings.DEBUG}")

# 应用关闭事件
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("FastAPI 应用正在关闭...")

# 注册路由
app.include_router(user_router)
app.include_router(patient_router)
app.include_router(report_router)
app.include_router(questionnaire_router)
app.include_router(upload_router)

@app.get("/")
async def root():
    return {"message": "Welcome to FastAPI Demo"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False) 