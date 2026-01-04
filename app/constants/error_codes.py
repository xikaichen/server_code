# 业务和HTTP响应码规范

# HTTP 状态码
SUCCESS = 200
CREATED = 201
NO_CONTENT = 204
BAD_REQUEST = 400
UNAUTHORIZED = 401
FORBIDDEN = 403
NOT_FOUND = 404
TOO_MANY_REQUESTS = 429
CONFLICT = 409
UNPROCESSABLE_ENTITY = 422
INTERNAL_SERVER_ERROR = 500
BAD_GATEWAY = 502
SERVICE_UNAVAILABLE = 503

# 业务自定义 code（1000+）
USER_OR_PASSWORD_ERROR = 1001
USER_ALREADY_EXISTS = 1002
BUSINESS_ERROR = 1003
DATABASE_ERROR = 1004
TOKEN_INVALID_OR_EXPIRED = 1005
# ... 可继续扩展

# code 到默认 message 的映射（可选）
CODE_MESSAGES = {
    SUCCESS: "success",
    CREATED: "created",
    NO_CONTENT: "no content",
    BAD_REQUEST: "bad request",
    UNAUTHORIZED: "unauthorized",
    FORBIDDEN: "forbidden",
    NOT_FOUND: "not found",
    TOO_MANY_REQUESTS: "too many requests",
    CONFLICT: "conflict",
    UNPROCESSABLE_ENTITY: "unprocessable entity",
    INTERNAL_SERVER_ERROR: "internal server error",
    BAD_GATEWAY: "bad gateway",
    SERVICE_UNAVAILABLE: "service unavailable",
    USER_OR_PASSWORD_ERROR: "invalid username or password",
    USER_ALREADY_EXISTS: "user already exists",
    BUSINESS_ERROR: "business error",
    DATABASE_ERROR: "database error",
    TOKEN_INVALID_OR_EXPIRED: "token invalid or expired",
} 