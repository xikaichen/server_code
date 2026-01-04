from fastapi import HTTPException

def http_404_exception(detail: str = "资源未找到"):
    raise HTTPException(status_code=404, detail=detail)

def http_400_exception(detail: str = "请求错误"):
    raise HTTPException(status_code=400, detail=detail)