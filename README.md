# 悦凯眼科服务后端

这是一个基于 FastAPI 框架的眼科服务后端项目，提供用户管理、患者管理、报告管理、问卷管理等核心功能。

## 目录

- [功能特性](#功能特性)
- [项目结构](#项目结构)
- [安装与运行](#安装与运行)
- [数据库表结构](#数据库表结构)
- [RQ Worker 部署](#rq-worker-部署)
- [部署到线上服务器](#部署到线上服务器)
- [API 端点](#api-端点)
- [技术栈](#技术栈)
- [开发说明](#开发说明)
- [常见问题](#常见问题)

## 功能特性

- ✅ 用户认证与授权（JWT Token）
- ✅ 短信验证码登录
- ✅ 用户信息管理
- ✅ 患者信息管理
- ✅ 问卷管理
- ✅ 检查报告管理
- ✅ 文件上传功能
- ✅ AI 报告分析（异步任务）
- ✅ 自动数据库初始化（支持线上部署）

## 项目结构

```
.
├── app/                       # 应用主目录
│   ├── __init__.py
│   ├── config.py              # 配置文件
│   ├── constants/             # 常量定义
│   │   └── error_codes.py     # 错误码定义
│   ├── middleware/            # 中间件
│   │   └── auth_middleware.py # 认证中间件
│   ├── models/                # 数据模型
│   │   ├── user.py            # 用户模型
│   │   ├── patient.py         # 患者模型
│   │   ├── questionnaire.py   # 问卷模型
│   │   ├── report.py          # 报告模型
│   │   └── response.py        # 响应模型
│   ├── routers/               # 路由
│   │   ├── user.py            # 用户路由
│   │   ├── patient.py         # 患者路由
│   │   ├── questionnaire.py   # 问卷路由
│   │   ├── report.py          # 报告路由
│   │   └── upload.py          # 文件上传路由
│   ├── services/              # 业务逻辑服务层
│   │   ├── ai_analysis.py     # AI 分析服务
│   │   └── report_analysis.py # 报告分析服务
│   └── utils/                 # 工具函数
│       ├── database.py        # 数据库连接
│       ├── security.py        # 安全相关（JWT、密码等）
│       ├── exceptions.py      # 异常处理
│       ├── htt_exceptions.py  # HTTP 异常
│       └── tasks.py           # 异步任务
├── worker/                    # RQ Worker 后台任务
│   ├── worker.py              # Worker 主程序
│   ├── start_worker.sh        # Worker 启动脚本
│   ├── check_redis_tasks.py   # Redis 任务检查工具
│   ├── logs/                  # Worker 日志目录
│   └── README.md              # Worker 详细文档
├── docs/                      # 项目文档
├── init_db.py                 # 数据库初始化脚本
├── main.py                    # 应用程序入口
├── requirements.txt           # 项目依赖
└── README.md                  # 项目说明
```

## 安装与运行

### 1. 环境要求

- Python 3.10+
- MySQL 5.7+ 或 MySQL 8.0+
- Redis（用于缓存和会话管理）

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置说明

项目使用 `pydantic_settings` 管理配置，配置读取优先级（从高到低）：

1. **系统环境变量**（推荐用于生产环境）
2. **`.env` 文件**（可选，如果存在）
3. **`app/config.py` 中的默认值**（开发环境可直接使用）

#### 方式一：直接使用默认配置（开发环境）

项目在 `app/config.py` 中已配置了默认值，可以直接运行，无需额外配置。

#### 方式二：使用环境变量（推荐用于生产环境）

在系统环境变量中设置：

```bash
# Linux/Mac
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=your_password
export MYSQL_DATABASE=yuekai_ophthalmology
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=1
export REDIS_PASSWORD=
export DEBUG=False

# Windows PowerShell
$env:MYSQL_HOST="localhost"
$env:MYSQL_PORT="3306"
$env:MYSQL_USER="root"
$env:MYSQL_PASSWORD="your_password"
# ... 其他配置类似
```

#### 方式三：使用 .env 文件（可选）

如果需要，可以复制项目根目录的 `env.example` 文件为 `.env`：

```bash
# Linux/Mac
cp env.example .env

# Windows
copy env.example .env
```

然后根据实际情况修改 `.env` 文件中的配置值。完整的配置项说明请参考 `env.example` 文件。

#### 方式四：直接修改 config.py

开发环境也可以直接修改 `app/config.py` 中的默认值。

**注意**：生产环境建议使用环境变量，避免敏感信息泄露。

### 5. 数据库初始化

#### 方式一：自动初始化（推荐）

应用启动时会自动执行数据库初始化脚本创建数据库表。使用 `CREATE TABLE IF NOT EXISTS` 语句，支持重复执行，不会因为表已存在而报错。

#### 方式二：手动初始化

如果需要手动初始化数据库：

```bash
# 1. 在 MySQL 中创建数据库（如果不存在）
mysql -u root -p
CREATE DATABASE yuekai_ophthalmology CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# 2. 执行 Python 初始化脚本
python init_db.py
```

### 6. 运行应用

#### 方式一：使用 uvicorn 命令（推荐）

```bash
# 开发模式（带热重载）
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 方式二：直接运行 Python 文件

```bash
# 开发模式（带热重载）
python main.py
```

**说明**：
- `python main.py` 会使用 `main.py` 中配置的默认参数（host="0.0.0.0", port=8000, reload=True）
- `uvicorn` 命令可以更灵活地配置参数，适合生产环境
- 两种方式都可以正常运行，推荐使用 `uvicorn` 命令以便更好地控制运行参数

访问以下地址查看 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 数据库表结构

项目包含以下数据表：

- **users** - 用户表
- **patients** - 患者表
- **questionnaires** - 问卷表
- **reports** - 检查报告表

所有表结构定义在数据库初始化脚本中，使用 MySQL InnoDB 引擎和 utf8mb4 字符集。表结构会在应用启动时自动创建。

## RQ Worker 部署

本项目使用 RQ（Redis Queue）处理后台异步任务（如报告分析、AI 分析等）。

### 开发环境

```bash
# 确保 Redis 服务已启动
python worker/worker.py
```

### 生产环境（宝塔面板）

**详细部署指南请查看：[worker/README.md](worker/README.md)**

**快速部署步骤**：

1. **安装 Supervisor 管理器**
   - 宝塔面板 -> 软件商店 -> 搜索 "Supervisor管理器" -> 安装

2. **添加守护进程**
   - 打开 Supervisor 管理器
   - 点击 "添加守护进程"
   - 填写以下信息：
     ```
     名称：rq-worker
     启动用户：root 或 www（根据项目用户）
     运行目录：项目根目录（如：/www/wwwroot/your_project）
     启动命令：bash worker/start_worker.sh
     ```

3. **启动服务**
   - 点击启动，查看日志确认启动成功
   - 日志文件：`worker/logs/worker.log`

**说明**：
- 使用启动脚本 `worker/start_worker.sh` 会自动激活 Python 项目环境
- 适用于宝塔 Python 项目管理器
- 确保 Redis 服务正常运行且配置正确

## 部署到线上服务器

### 宝塔面板部署

1. **准备数据库**
   - 在宝塔面板中创建 MySQL 数据库
   - 记录数据库名称、用户名、密码等信息

2. **配置环境变量**
   - 在系统环境变量中配置数据库连接信息（推荐）
   - 或使用宝塔面板的环境变量功能
   - 或直接修改 `app/config.py` 中的配置（不推荐用于生产环境）

3. **部署代码**
   - 将项目代码上传到服务器
   - 安装 Python 依赖：`pip install -r requirements.txt`

4. **自动初始化数据库**
   - 应用启动时会自动执行数据库初始化脚本创建所有表
   - 使用 `CREATE TABLE IF NOT EXISTS`，支持重复执行
   - 每次上线都会自动检查并创建缺失的表

5. **启动应用**
   - 使用进程管理器（如 PM2、Supervisor）管理应用进程
   - 或使用宝塔面板的进程管理器

### 注意事项

- **数据库必须提前创建**：脚本只会创建表，不会创建数据库。请在部署前先创建数据库。
- **数据库用户权限**：确保数据库用户有创建表的权限（CREATE、ALTER 等）
- **表已存在**：如果表已存在，`CREATE TABLE IF NOT EXISTS` 不会报错，可以安全重复执行
- **每次上线**：每次部署上线时，应用启动会自动执行初始化，确保表结构是最新的

## API 端点

### 用户相关

- `POST /api/v1/user/login/get_sms_code` - 获取短信验证码
- `POST /api/v1/user/login` - 验证码登录
- `POST /api/v1/user/logout` - 用户登出
- `GET /api/v1/user/info` - 获取用户信息（需要认证）
- `PUT /api/v1/user/info` - 更新用户信息（需要认证）

### 患者相关

- `GET /api/v1/patient` - 获取患者列表（需要认证）
- `POST /api/v1/patient` - 创建患者（需要认证）
- `GET /api/v1/patient/{patient_id}` - 获取患者详情（需要认证）
- `PUT /api/v1/patient/{patient_id}` - 更新患者信息（需要认证）
- `DELETE /api/v1/patient/{patient_id}` - 删除患者（需要认证）

### 问卷相关

- `GET /api/v1/questionnaire` - 获取问卷列表（需要认证）
- `POST /api/v1/questionnaire` - 创建问卷（需要认证）
- `GET /api/v1/questionnaire/{questionnaire_id}` - 获取问卷详情（需要认证）
- `PUT /api/v1/questionnaire/{questionnaire_id}` - 更新问卷（需要认证）
- `DELETE /api/v1/questionnaire/{questionnaire_id}` - 删除问卷（需要认证）

### 报告相关

- `GET /api/v1/report` - 获取报告列表（需要认证）
- `POST /api/v1/report` - 创建报告（需要认证）
- `GET /api/v1/report/{report_id}` - 获取报告详情（需要认证）
- `PUT /api/v1/report/{report_id}` - 更新报告（需要认证）
- `DELETE /api/v1/report/{report_id}` - 删除报告（需要认证）

### 文件上传

- `POST /api/v1/upload` - 上传文件（需要认证）

### 完整 API 文档

更多详细的 API 端点、请求参数、响应格式等信息，请访问：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 技术栈

### 核心框架
- **Web框架**: FastAPI - 现代、快速的 Python Web 框架
- **数据库**: MySQL 5.7+ / 8.0+ - 关系型数据库
- **数据库驱动**: PyMySQL - Python MySQL 客户端
- **ORM**: SQLAlchemy - Python SQL 工具包和 ORM

### 缓存与队列
- **缓存**: Redis - 内存数据结构存储
- **任务队列**: RQ (Redis Queue) - 基于 Redis 的简单任务队列

### 认证与安全
- **认证**: JWT (JSON Web Token) - 无状态身份验证
- **密码加密**: 使用安全的哈希算法

### 开发工具
- **API文档**: Swagger UI / ReDoc - 自动生成的交互式 API 文档

## 开发说明

### 项目架构

项目采用分层架构设计：

- **路由层** (`app/routers/`): 处理 HTTP 请求和响应
- **服务层** (`app/services/`): 业务逻辑处理
- **模型层** (`app/models/`): 数据模型定义
- **工具层** (`app/utils/`): 通用工具函数
- **中间件** (`app/middleware/`): 请求拦截和处理

### 添加新的数据模型

1. 在 `app/models/` 目录下创建模型文件
2. 在数据库初始化脚本中添加对应的 `CREATE TABLE` 语句
3. 在 `init_db.py` 中导入新模型（如果使用 ORM 方式）

### 添加新的路由

1. 在 `app/routers/` 目录下创建路由文件
2. 在 `main.py` 中注册路由：`app.include_router(your_router, prefix="/api/v1")`

### 添加新的服务

1. 在 `app/services/` 目录下创建服务文件
2. 在路由中导入并使用服务类

### 异步任务处理

1. 在 `app/utils/tasks.py` 中定义任务函数
2. 使用 RQ 将任务加入队列：`from app.utils.tasks import queue; queue.enqueue(task_function, args)`
3. 确保 RQ Worker 正在运行以处理任务

### 错误处理

- 使用 `app/utils/exceptions.py` 中定义的自定义异常
- 使用 `app/utils/htt_exceptions.py` 中的 HTTP 异常处理
- 错误码定义在 `app/constants/error_codes.py` 中

## 常见问题

### 数据库连接失败

- 检查 MySQL 服务是否正常运行
- 确认数据库配置是否正确（检查环境变量、`.env` 文件或 `app/config.py`）
- 检查数据库用户是否有足够的权限
- 确认数据库是否已创建

### Redis 连接失败

- 检查 Redis 服务是否正常运行
- 确认 Redis 配置是否正确（检查环境变量、`.env` 文件或 `app/config.py`）
- 检查 Redis 密码是否正确（如果有）

### Worker 无法启动

- 确保 Redis 服务正常运行
- 检查 `worker/start_worker.sh` 脚本权限：`chmod +x worker/start_worker.sh`
- 查看日志文件：`worker/logs/worker.log`

### 端口被占用

- 修改 `main.py` 中的端口配置
- 或使用不同的端口启动：`uvicorn main:app --port 8001`

## 许可证

[根据实际情况填写]
