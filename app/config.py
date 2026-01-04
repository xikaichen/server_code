from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    
    # Database settings
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "rLRP77.."
    MYSQL_DATABASE: str = "yuekai_ophthalmology"
    
    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 1
    REDIS_PASSWORD: str = ""  # 如果Redis没有密码，留空
    
    # AIGC settings
    AIGC_API_URL: str = "https://aigc.x-see.cn"
    AIGC_API_KEY: str = "sk-AWmyjBSfvBsKCO929nU9toZG1rTJ8soAZzOV4wCLju9NOdcU"
    
    # RQ settings
    RQ_JOB_TIMEOUT: int = 1800  # 任务超时时间（秒），30分钟
    RQ_JOB_RESULT_TTL: int = 86400  # 任务结果保留时间（秒），24小时
    RQ_JOB_FAILURE_TTL: int = 86400  # 失败任务保留时间（秒），24小时
    RQ_JOB_RETRY_MAX: int = 3  # 最大重试次数
    RQ_JOB_RETRY_DELAY: int = 60  # 重试延迟（秒），1分钟
    
    # Invite code settings
    INVITE_CODES: List[str] = ["yuekaiyanke"]  # 有效的邀请码列表，可通过环境变量配置
    
    # SMS verification code platform settings
    SMS_PLATFORM_URL: str = "https://push.spug.cc/send/9npGV81z3ymybAN1"  # 验证码平台URL
    SMS_PLATFORM_NAME: str = "悦凯眼科"  # 验证码平台发送方名称

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
    
    class Config:
        env_file = ".env"

settings = Settings() 