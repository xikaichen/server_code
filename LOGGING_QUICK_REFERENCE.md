# 日志系统快速参考

## 快速开始

### 在新文件中添加日志

```python
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# 使用
logger.info("操作成功")
logger.error("操作失败", exc_info=True)
```

## 常用日志模式

### 1. 记录函数入口
```python
def create_report(report_id: int):
    logger.info(f"开始创建报告，ID: {report_id}")
    # ... 业务逻辑
```

### 2. 记录成功操作
```python
logger.info(f"报告 {report_id} 创建成功")
```

### 3. 记录警告
```python
logger.warning(f"请求参数验证失败: {error_messages}")
```

### 4. 记录错误（带堆栈跟踪）
```python
try:
    # 业务逻辑
except Exception as e:
    logger.error(f"创建报告失败: {e}", exc_info=True)
    raise
```

### 5. 记录调试信息
```python
logger.debug(f"中间结果: {intermediate_data}")
```

## 日志文件位置

| 文件 | 内容 | 用途 |
|------|------|------|
| `logs/app.log` | 所有日志 | 完整的应用运行记录 |
| `logs/error.log` | 仅错误 | 快速定位问题 |
| `worker/logs/worker.log` | Worker日志 | 后台任务日志 |

## 查看日志命令

```bash
# 实时查看应用日志
tail -f logs/app.log

# 实时查看错误日志
tail -f logs/error.log

# 查看最近100行
tail -n 100 logs/app.log

# 搜索特定关键词
grep "报告" logs/app.log

# 搜索错误
grep "ERROR" logs/app.log

# 查看今天的日志
grep "2025-01-04" logs/app.log

# 统计错误数量
grep -c "ERROR" logs/app.log
```

## 日志级别选择指南

| 级别 | 使用场景 | 示例 |
|------|----------|------|
| DEBUG | 详细调试信息 | `logger.debug(f"变量值: {var}")` |
| INFO | 正常操作 | `logger.info("用户登录成功")` |
| WARNING | 警告但不影响运行 | `logger.warning("参数验证失败")` |
| ERROR | 错误需要关注 | `logger.error("数据库连接失败", exc_info=True)` |
| CRITICAL | 严重错误 | `logger.critical("系统崩溃")` |

## 最佳实践

### ✅ 推荐做法

```python
# 1. 使用 f-string 格式化
logger.info(f"处理报告 {report_id}")

# 2. 错误时记录堆栈
logger.error(f"失败: {e}", exc_info=True)

# 3. 记录关键业务操作
logger.info(f"用户 {user_id} 创建了报告 {report_id}")

# 4. 使用合适的日志级别
logger.warning("Redis 连接缓慢")  # 不是 error
```

### ❌ 避免做法

```python
# 1. 不要使用 print
print("这不会被记录")  # ❌

# 2. 不要记录敏感信息
logger.info(f"密码: {password}")  # ❌

# 3. 不要在循环中过度记录
for item in items:
    logger.info(f"处理 {item}")  # ❌ 太多日志

# 4. 不要吞掉异常
except Exception:
    pass  # ❌ 应该记录
```

## 配置调整

### 修改日志级别

编辑 `app/config.py`:
```python
DEBUG: bool = False  # 生产环境设为 False
```

### 修改日志格式

编辑 `app/utils/logging_config.py`:
```python
LOG_FORMAT = '你的格式'
```

### 修改文件大小限制

编辑 `app/utils/logging_config.py`:
```python
maxBytes=20 * 1024 * 1024,  # 改为 20MB
backupCount=10,  # 保留 10 个备份
```

## 故障排查

### 问题：日志没有输出

**检查清单**:
1. ✅ `logs/` 目录是否存在且有写入权限
2. ✅ `main.py` 中是否调用了 `setup_logging()`
3. ✅ 模块中是否正确导入 `get_logger(__name__)`
4. ✅ 日志级别是否正确（DEBUG 模式下才显示 debug 日志）

### 问题：日志文件太大

**解决方案**:
- 日志会自动轮转，无需担心
- 如需手动清理：`rm logs/app.log.*`

### 问题：找不到特定日志

**解决方案**:
```bash
# 使用 grep 搜索
grep -r "关键词" logs/

# 按时间范围搜索
grep "2025-01-04 10:" logs/app.log
```

