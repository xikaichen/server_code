from fastapi import HTTPException
from app.models import error_codes

def http_404_exception(detail: str = "Resource not found"):
    raise HTTPException(status_code=error_codes.NOT_FOUND, detail=detail) 