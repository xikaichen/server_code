# 集中式日志配置说明

## 概述

已为 yuekai_app 服务器配置了集中式日志系统，所有日志消息现在都会输出到统一的位置。

## 配置内容

### 1. 日志配置模块
**文件**: `app/utils/logging_config.py`

提供了集中式日志配置，包括：
- 控制台输出（INFO 及以上级别）
- 应用日志文件 `logs/app.log`（所有日志）
- 错误日志文件 `logs/error.log`（仅错误）
- 日志轮转：单个文件最大 10MB，保留 5 个备份

### 2. 日志格式
```
YYYY-MM-DD HH:MM:SS [LEVEL] module_name:line_number - message
```

示例：
```
2025-01-04 10:30:45 [INFO] main:97 - FastAPI 应用启动成功
2025-01-04 10:31:12 [ERROR] app.routers.report:140 - 创建报告失败: Connection timeout
```

### 3. 日志输出位置

所有日志会同时输出到：
1. **控制台** - 方便开发调试
2. **logs/app.log** - 完整的应用日志
3. **logs/error.log** - 仅错误日志（便于快速定位问题）

## 已更新的文件

### 主应用
- ✅ `main.py` - 初始化日志系统，替换所有 print 为 logger

### 路由模块
- ✅ `app/routers/user.py` - 用户相关操作日志
- ✅ `app/routers/report.py` - 报告相关操作日志
- ✅ `app/routers/upload.py` - 文件上传日志

### 服务模块
- ✅ `app/services/ai_analysis.py` - AI 分析日志
- ✅ `app/services/report_analysis.py` - 报告分析日志（已有 logger，保持不变）

### 工具模块
- ✅ `app/utils/tasks.py` - 任务队列日志（已有 logger，保持不变）

## 使用方法

### 在新模块中使用日志

```python
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# 使用日志
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息", exc_info=True)  # exc_info=True 会记录完整的堆栈跟踪
logger.critical("严重错误")
```

### 日志级别说明

- **DEBUG**: 详细的调试信息（仅在 DEBUG=True 时输出）
- **INFO**: 一般信息，如操作成功、状态变化
- **WARNING**: 警告信息，如参数验证失败
- **ERROR**: 错误信息，如操作失败、异常
- **CRITICAL**: 严重错误，如系统崩溃

## 配置选项

在 `app/config.py` 中：
- `DEBUG = True` - 日志级别为 DEBUG
- `DEBUG = False` - 日志级别为 INFO（生产环境推荐）

## 日志文件管理

### 自动轮转
- 当日志文件达到 10MB 时自动创建新文件
- 旧文件会被重命名为 `app.log.1`, `app.log.2` 等
- 最多保留 5 个备份文件

### 查看日志
```bash
# 查看最新的应用日志
tail -f logs/app.log

# 查看最新的错误日志
tail -f logs/error.log

# 搜索特定错误
grep "ERROR" logs/app.log

# 查看今天的日志
grep "2025-01-04" logs/app.log
```

## 与 Worker 日志的区别

- **应用日志** (`logs/app.log`): FastAPI 主应用的日志
- **Worker 日志** (`worker/logs/worker.log`): RQ Worker 后台任务的日志

两者独立配置，互不影响。

## 注意事项

1. **日志目录已添加到 .gitignore**，不会提交到版本控制
2. **生产环境建议**：
   - 设置 `DEBUG=False`
   - 定期备份重要日志
   - 考虑使用日志聚合服务（如 ELK、Loki 等）
3. **性能考虑**：日志写入是异步的，不会显著影响性能

## 测试日志配置

启动服务器后，检查：
1. 控制台是否显示日志
2. `logs/app.log` 文件是否创建并写入
3. 触发错误时 `logs/error.log` 是否记录

```bash
# 启动服务器
python main.py

# 或使用 uvicorn
uvicorn main:app --reload
```

## 故障排查

如果日志没有输出：
1. 检查 `logs/` 目录是否有写入权限
2. 检查 `setup_logging()` 是否在 `main.py` 中被调用
3. 检查是否正确导入 `get_logger(__name__)`

