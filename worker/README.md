# RQ Worker 使用指南

本文档包含 RQ Worker 的完整使用说明，包括部署、持久化机制、重试机制和中断处理。

## 目录

1. [部署指南](#部署指南)
2. [任务持久化机制](#任务持久化机制)
3. [重试机制](#重试机制)
4. [中断处理机制](#中断处理机制)

---

## 部署指南

### 准备工作

1. **确保 Redis 已安装并运行**
   - 宝塔面板 -> 软件商店 -> 安装 Redis
   - 确保 Redis 服务正常运行

2. **配置环境变量**
   - 确保项目根目录有 `.env` 文件
   - 配置好 Redis 连接信息（特别是 `REDIS_PASSWORD`）

### 宝塔面板部署步骤

#### 方式一：使用 Supervisor 管理器（推荐）

1. **安装 Supervisor**
   - 宝塔面板 -> 软件商店 -> 搜索 "Supervisor管理器" -> 安装

2. **添加守护进程**
   - 打开 Supervisor 管理器
   - 点击 "添加守护进程"
   - 填写以下信息：
     ```
     名称：rq-worker
     启动用户：root 或 www（根据你的项目用户）
     运行目录：/www/wwwroot/你的项目目录（或包含项目的父目录）
     启动命令：bash worker/start_worker.sh
     ```
   
   **推荐使用启动脚本**（`worker/start_worker.sh`）：
   - 脚本会自动激活 Python 项目环境（使用 `py-project-env`）
   - 适用于宝塔 Python 项目管理器
   - 通用性强，兼容性好
   
   **其他方式**（备选）：
   - 如果使用虚拟环境，启动命令改为：
     ```
     /www/server/python/你的虚拟环境路径/bin/python worker/worker.py
     ```
   - 例如：
     ```
     /www/server/python/venv/bin/python worker/worker.py
     ```

3. **启动服务**
   - 点击 "启动"
   - 查看状态显示为 "运行中" 即成功

4. **查看日志**
   - 在 Supervisor 管理器中点击 "日志" 查看实时日志
   - 或者查看项目目录下的 `worker/logs/worker.log` 文件

#### 方式二：使用进程管理器（PM2）

如果项目使用 PM2 管理，可以添加 RQ Worker：

```bash
# SSH 进入服务器
cd /www/wwwroot/你的项目目录

# 添加 RQ Worker 进程
pm2 start worker/worker.py --name rq-worker --interpreter python

# 保存进程列表
pm2 save

# 设置开机自启
pm2 startup
```

### 验证部署

1. **查看日志**
   ```bash
   tail -f worker/logs/worker.log
   ```
   
   看到以下内容说明启动成功：
   ```
   成功连接到 Redis: localhost:6379/1
   监听队列: report_analysis
   RQ Worker 已启动，开始处理任务...
   ```

2. **检查队列状态**
   ```bash
   python worker/check_redis_tasks.py
   ```

3. **测试任务处理**
   - 在应用中提交一个需要后台处理的任务
   - 观察日志文件，应该能看到任务处理过程

### 常见问题

#### 1. Worker 启动失败

**检查项**：
- Redis 是否运行：`redis-cli ping`
- `.env` 文件中的 Redis 配置是否正确
- Python 环境是否正确

**解决方法**：
```bash
# 直接运行 worker 查看错误信息
python worker/worker.py
```

#### 2. 无法连接到 Redis

**检查项**：
- Redis 密码是否配置正确
- Redis 是否允许外部连接（生产环境建议配置密码）

**解决方法**：
```bash
# 测试 Redis 连接
redis-cli -h localhost -p 6379 -a 你的密码 ping
```

#### 3. 日志文件不存在

- Worker 会自动创建 `worker/logs` 目录和日志文件
- 如果目录创建失败，检查文件权限

#### 4. 任务不执行

**检查项**：
- Worker 是否正常运行
- 队列名称是否正确（默认：`report_analysis`）
- Redis 连接是否正常

**解决方法**：
```bash
# 查看队列中的任务
python worker/check_redis_tasks.py

# 查看 Worker 日志
tail -f worker/logs/worker.log
```

### 多实例部署（可选）

如果需要提高处理能力，可以启动多个 Worker 实例：

1. 在 Supervisor 中再添加一个守护进程：
   ```
   名称：rq-worker-2
   启动命令：python worker/worker.py
   ```

2. 或者使用 PM2：
   ```bash
   pm2 start worker/worker.py --name rq-worker-2 --interpreter python
   ```

多个 Worker 会同时处理同一个队列中的任务，自动负载均衡。

### 日常维护

#### 重启 Worker

- **Supervisor**：在管理界面点击 "重启"
- **PM2**：`pm2 restart rq-worker`

#### 查看日志

- 项目目录下的 `worker/logs/worker.log`
- Supervisor 管理界面查看实时日志
- PM2：`pm2 logs rq-worker`

#### 停止 Worker

- **Supervisor**：在管理界面点击 "停止"
- **PM2**：`pm2 stop rq-worker`

### 监控建议

虽然项目比较简单，但建议：

1. **定期查看日志**：检查是否有错误信息
2. **监控队列长度**：如果任务积压过多，考虑增加 Worker 实例
3. **设置告警**：如果使用监控系统，可以监控 Worker 进程是否运行

---

## 任务持久化机制

### 🤔 核心问题：Worker 停止后，任务信息存储在哪里？

**答案：任务信息存储在 Redis 中，而不是 Worker 的内存中！**

### 📦 RQ 的存储架构

#### 1. 三层架构

```
┌─────────────┐
│  FastAPI    │  创建任务，将任务加入队列
│  Application│
└──────┬──────┘
       │ enqueue()
       ↓
┌─────────────┐
│    Redis    │  ← 任务信息永久存储在这里！
│   (持久化)   │
└──────┬──────┘
       │ 读取任务
       ↓
┌─────────────┐
│   Worker    │  从 Redis 读取任务并执行
│  (临时进程)  │
└─────────────┘
```

#### 2. 关键点

- **Redis = 持久化存储**：所有任务信息都存储在 Redis 中
- **Worker = 临时执行器**：Worker 只是从 Redis 读取任务并执行
- **Worker 停止不影响任务**：任务仍然在 Redis 中，等待新的 Worker 处理

### 🔍 RQ 在 Redis 中的数据结构

#### 1. 队列（Queue）

RQ 使用 Redis 的 List 数据结构存储队列：

```
Redis Key: rq:queue:report_analysis
Redis Type: List
存储内容: [job_id1, job_id2, job_id3, ...]
```

#### 2. 任务信息（Job）

每个任务的信息存储在 Redis Hash 中：

```
Redis Key: rq:job:{job_id}
Redis Type: Hash
存储内容:
  - created_at: 创建时间
  - enqueued_at: 入队时间
  - started_at: 开始执行时间
  - ended_at: 结束时间
  - status: 状态（queued/started/finished/failed）
  - func_name: 函数名
  - args: 参数（pickle 序列化）
  - result: 结果（pickle 序列化）
  - retry: 重试配置
  - ...
```

#### 3. 任务状态跟踪

```
rq:job:{job_id} → 任务详细信息
rq:queue:{queue_name} → 队列中的任务 ID 列表
rq:worker:{worker_name} → Worker 当前执行的任务
rq:failed:{job_id} → 失败的任务信息
```

### 🔄 Worker 停止和重启的完整流程

#### 场景1：任务在队列中（queued）

```
时间线：
--------
10:00 - 任务入队，存储在 Redis: rq:queue:report_analysis = [job_123]
10:01 - Worker 启动，从 Redis 读取队列
10:02 - Worker 停止（Ctrl+C 或崩溃）
        ↓
        Redis 中的任务仍然存在！
        rq:queue:report_analysis = [job_123]  ← 还在！
        rq:job:job_123 = {...}  ← 任务信息还在！
10:05 - 新的 Worker 启动
10:06 - 新 Worker 从 Redis 读取队列，发现 job_123
10:07 - 新 Worker 开始执行 job_123
```

#### 场景2：任务正在执行（started）

```
时间线：
--------
10:00 - Worker 从队列取出任务 job_123
10:01 - 任务状态变为 started
        Redis: rq:job:job_123.status = "started"
        Redis: rq:worker:worker_1.current_job = "job_123"
10:02 - Worker 崩溃或停止
        ↓
        Redis 中的任务信息仍然存在！
        rq:job:job_123.status = "started"  ← 状态还在！
        rq:queue:report_analysis = []  ← 队列已空（任务已取出）
10:05 - RQ 的清理机制检测到 Worker 已停止
10:06 - 将任务状态从 "started" 改为 "failed"
        Redis: rq:job:job_123.status = "failed"
10:07 - 如果配置了 retry，任务会重新入队
        Redis: rq:queue:report_analysis = [job_123]  ← 重新入队！
10:10 - 新 Worker 启动，从队列读取任务
10:11 - 新 Worker 开始执行 job_123（重试）
```

### 🔍 如何查看 Redis 中的任务

#### 方法1：使用 Redis CLI

```bash
# 连接到 Redis
redis-cli -h localhost -p 6379 -n 1

# 查看队列中的任务
LRANGE rq:queue:report_analysis 0 -1

# 查看任务详细信息
HGETALL rq:job:report_analysis_123

# 查看所有任务
KEYS rq:job:*

# 查看失败的任务
KEYS rq:failed:*
```

#### 方法2：使用 Python 代码

```python
from app.utils.database import get_redis_client_for_rq
from rq import Queue
from rq.job import Job

redis_conn = get_redis_client_for_rq()
queue = Queue('report_analysis', connection=redis_conn)

# 查看队列中的任务数量
print(f"队列中的任务数: {len(queue)}")

# 查看所有任务
for job_id in queue.job_ids:
    job = Job.fetch(job_id, connection=redis_conn)
    print(f"任务 {job_id}: 状态={job.get_status()}, 创建时间={job.created_at}")

# 查看失败的任务
failed_queue = Queue('failed', connection=redis_conn)
for job_id in failed_queue.job_ids:
    job = Job.fetch(job_id, connection=redis_conn)
    print(f"失败任务 {job_id}: {job.exc_info}")
```

### 🎯 关键理解点

#### 1. Worker 不存储任务

```
❌ 错误理解：
Worker 停止 → 任务丢失

✅ 正确理解：
Worker 停止 → 任务仍在 Redis 中 → 新 Worker 继续处理
```

#### 2. Redis 是持久化的

```
任务入队 → 立即存储到 Redis → 即使应用重启，任务仍在
Worker 停止 → Redis 中的任务不受影响
新 Worker 启动 → 从 Redis 读取任务 → 继续处理
```

#### 3. 任务状态转换

```
queued (队列中)
  ↓ Worker 取出
started (执行中)
  ↓ 执行完成
finished (成功) 或 failed (失败)
  ↓ 如果配置了 retry 且失败
queued (重新入队，重试)
```

### ⚠️ 注意事项

1. **Redis 数据持久化**：确保 Redis 配置了持久化（RDB 或 AOF），否则 Redis 重启会丢失数据
2. **Redis 连接**：Worker 和应用必须连接到同一个 Redis 实例
3. **任务去重**：使用 `job_id` 可以防止重复任务
4. **任务清理**：配置 `result_ttl` 和 `failure_ttl` 可以自动清理旧任务

---

## 重试机制

### 📖 重试机制工作原理

#### 1. 基本概念

RQ 的重试机制是通过 `Retry` 对象实现的。当你创建一个任务时，如果配置了 `retry` 参数，RQ 会在任务失败时自动重试。

#### 2. 重试触发条件

重试会在以下情况触发：

1. **任务抛出异常**：函数执行时抛出任何异常
2. **任务超时**：任务执行时间超过 `job_timeout`
3. **Worker 崩溃**：Worker 进程意外终止，正在执行的任务失败

#### 3. 重试流程

```
任务入队 → Worker 取出任务 → 执行任务
                              ↓
                        任务执行失败（异常/超时）
                              ↓
                    RQ 检查是否有 retry 配置
                              ↓
                        有 retry 配置？
                    ↙                    ↘
                  是                      否
                  ↓                       ↓
            等待 interval 秒         任务永久失败
                  ↓
            重新放回队列（状态：queued）
                  ↓
            Worker 重新取出执行
                  ↓
            检查重试次数 < max？
                  ↓
            是 → 继续重试
            否 → 任务永久失败
```

#### 4. 实际示例

假设配置了 `Retry(max=3, interval=60)`：

```
时间线：
--------
00:00 - 任务第1次执行开始
00:05 - 任务执行失败（抛出异常）
00:05 - RQ 捕获异常，检查到有 retry 配置
00:05 - 等待 60 秒（interval）
01:05 - 任务重新放回队列（第1次重试）
01:05 - Worker 取出任务，第2次执行开始
01:10 - 任务执行失败（抛出异常）
01:10 - RQ 捕获异常，检查重试次数（1 < 3，继续重试）
01:10 - 等待 60 秒
02:10 - 任务重新放回队列（第2次重试）
02:10 - Worker 取出任务，第3次执行开始
02:15 - 任务执行失败（抛出异常）
02:15 - RQ 捕获异常，检查重试次数（2 < 3，继续重试）
02:15 - 等待 60 秒
03:15 - 任务重新放回队列（第3次重试）
03:15 - Worker 取出任务，第4次执行开始
03:20 - 任务执行失败（抛出异常）
03:20 - RQ 捕获异常，检查重试次数（3 >= 3，达到最大重试次数）
03:20 - 任务永久失败，不再重试
```

### 代码示例

#### 配置重试（在 `enqueue_report_analysis` 中）

```python
from rq import Retry

# 创建重试配置
retry = Retry(
    max=3,      # 最多重试3次（总共执行4次）
    interval=60 # 每次失败后等待60秒
)

# 入队任务时配置重试
job = queue.enqueue(
    process_report_analysis,
    report_id,
    retry=retry,  # 关键：告诉 RQ 这个任务要自动重试
)
```

#### 任务函数（在 `process_report_analysis` 中）

```python
def process_report_analysis(report_id: int):
    try:
        # 执行任务逻辑
        result = do_something()
        return result
    except Exception as e:
        # 重要：必须重新抛出异常，让 RQ 知道任务失败
        # 如果不抛出，RQ 认为任务成功，不会重试
        logger.error(f"任务失败: {e}")
        raise  # 重新抛出异常，触发重试
```

### 关键点

#### ✅ 正确做法

```python
def process_task():
    try:
        # 执行可能失败的操作
        result = risky_operation()
        return result
    except Exception as e:
        # 记录错误
        logger.error(f"错误: {e}")
        # 重新抛出异常，让 RQ 触发重试
        raise
```

#### ❌ 错误做法

```python
def process_task():
    try:
        result = risky_operation()
        return result
    except Exception as e:
        # 错误：捕获异常后不抛出
        # RQ 会认为任务成功完成，不会重试
        logger.error(f"错误: {e}")
        return None  # 不要这样做！
```

### 监控重试

你可以通过以下方式查看任务的重试状态：

```python
from rq.job import Job
from app.utils.database import get_redis_client_for_rq

redis_conn = get_redis_client_for_rq()
job = Job.fetch('report_analysis_123', connection=redis_conn)

print(f"任务状态: {job.get_status()}")  # queued, started, finished, failed
print(f"重试次数: {job.retries_left}")   # 剩余重试次数
print(f"是否失败: {job.is_failed}")      # 是否失败
```

### 配置参数说明

在 `app/config.py` 中：

```python
RQ_JOB_RETRY_MAX: int = 3   # 最大重试次数（不包括首次执行）
RQ_JOB_RETRY_DELAY: int = 60 # 重试延迟（秒）
```

- `max=3` 意味着：1次初始执行 + 3次重试 = 总共最多执行4次
- `interval=60` 意味着：每次失败后等待60秒再重试

---

## 中断处理机制

### 🤔 核心问题：任务执行途中 Worker 被关闭，会自动重试吗？

**答案：是的，会自动重试！但需要满足以下条件：**

1. ✅ 任务配置了 `retry` 参数
2. ✅ 新的 Worker 启动时会自动清理并重试
3. ⚠️ 如果所有 Worker 都停止，需要等待新的 Worker 启动才会检测和重试

### 🔄 完整流程

#### 场景：任务执行途中 Worker 被关闭

```
时间线：
--------
10:00:00 - Worker 从队列取出任务 job_123
10:00:01 - 任务状态变为 "started"
           Redis: rq:job:job_123.status = "started"
           Redis: rq:worker:worker_1.current_job = "job_123"
           Redis: rq:queue:report_analysis = []  (任务已从队列取出)
           
10:00:30 - 任务正在执行中（例如：正在调用 AI API）
10:00:31 - Worker 被关闭（Ctrl+C 或崩溃）
           ↓
           Worker 进程终止
           任务状态仍然是 "started"（因为 Worker 没有机会更新状态）
           
10:00:32 - Redis 中的状态：
           rq:job:job_123.status = "started"  ← 仍然是 started
           rq:worker:worker_1.current_job = "job_123"  ← Worker 记录还在
           
10:01:00 - 新的 Worker 启动
10:01:01 - RQ 的清理机制（cleanup）自动运行
           ↓
           检测到 worker_1 已经不存在（心跳超时）
           检测到 job_123 状态是 "started" 但 Worker 已停止
           将任务状态改为 "failed"
           ↓
           如果任务配置了 retry：
           - 检查重试次数 < max？
           - 是 → 等待 interval 秒后重新入队
           - 否 → 任务永久失败
           
10:01:02 - 任务重新入队（如果配置了 retry）
           Redis: rq:queue:report_analysis = [job_123]
           Redis: rq:job:job_123.status = "queued"
           
10:01:03 - Worker 从队列取出任务
10:01:04 - 任务重新执行（重试）
```

### 🔍 RQ 的清理机制（Cleanup）

#### 1. 自动清理

RQ Worker 在启动时会自动清理"僵尸任务"：

- **僵尸任务**：状态是 "started" 但对应的 Worker 已经不存在
- **检测方式**：检查 Worker 的心跳（heartbeat）
- **处理方式**：将任务状态改为 "failed"，然后根据 retry 配置决定是否重试

#### 2. 清理时机

清理在以下时机自动执行：

1. **Worker 启动时**：检查所有 "started" 状态的任务
2. **Worker 运行中**：定期检查（通过心跳机制）
3. **手动清理**：可以使用 RQ 的命令行工具

#### 3. Worker 心跳机制

```
Worker 运行时会定期向 Redis 发送心跳：
rq:worker:{worker_name}.heartbeat = <timestamp>

如果心跳超过一定时间（默认 420 秒）没有更新，
说明 Worker 已经停止，任务会被标记为失败。
```

### ✅ 当前配置已支持自动重试

你的代码已经配置了重试机制：

```python
# app/utils/tasks.py
retry = Retry(
    max=3,      # 最多重试3次
    interval=60 # 每次失败后等待60秒
)

job = queue.enqueue(
    process_report_analysis,
    report_id,
    retry=retry,  # ✅ 已配置重试
)
```

所以，**任务执行途中 Worker 被关闭，会自动重试！**

### 📊 不同场景的处理

#### 场景1：Worker 正常关闭（Ctrl+C）

```
10:00 - 任务正在执行
10:01 - 收到 SIGINT/SIGTERM 信号
10:02 - Worker 尝试优雅关闭：
        - 等待当前任务完成（如果可能）
        - 或者标记任务为失败
10:03 - 如果任务被标记为失败且配置了 retry → 自动重试
```

#### 场景2：Worker 崩溃（进程异常终止）

```
10:00 - 任务正在执行
10:01 - Worker 进程崩溃（内存溢出、段错误等）
10:02 - 任务状态仍然是 "started"
10:03 - 新 Worker 启动时检测到僵尸任务
10:04 - 标记为失败，如果配置了 retry → 自动重试
```

#### 场景3：Worker 被强制杀死（kill -9）

```
10:00 - 任务正在执行
10:01 - kill -9 <worker_pid>（强制杀死）
10:02 - Worker 立即终止，无法执行清理
10:03 - 任务状态仍然是 "started"
10:04 - 新 Worker 启动时检测到僵尸任务
10:05 - 标记为失败，如果配置了 retry → 自动重试
```

### ⚠️ 重要注意事项

#### 1. 清理不是实时的

- 如果所有 Worker 都停止，需要等待新的 Worker 启动才会清理
- 清理延迟取决于 Worker 启动时间

#### 2. 心跳超时时间

- 默认心跳超时：420 秒（7 分钟）
- 如果任务执行时间超过 7 分钟，可能会被误判为僵尸任务

#### 3. 任务幂等性

- 确保任务函数是幂等的（多次执行结果相同）
- 因为重试会重新执行整个任务，而不是从中断处继续

### 🔧 如何验证

#### 测试步骤

1. **启动 Worker**
   ```bash
   python worker.py
   ```

2. **创建一个长时间运行的任务**
   - 通过 API 创建报告（会触发 AI 分析任务）

3. **在任务执行途中关闭 Worker**
   ```bash
   # 在另一个终端
   # 找到 Worker 进程
   ps aux | grep worker.py
   # 强制杀死（模拟崩溃）
   kill -9 <worker_pid>
   ```

4. **查看任务状态**
   ```bash
   python worker/check_redis_tasks.py
   # 应该看到任务状态是 "started" 或 "failed"
   ```

5. **重新启动 Worker**
   ```bash
   python worker.py
   ```

6. **观察日志**
   - Worker 启动时会清理僵尸任务
   - 如果配置了 retry，任务会重新入队
   - Worker 会重新执行任务

### 🎯 最佳实践

1. **配置重试**：✅ 已配置
2. **任务幂等性**：确保 `process_report_analysis` 可以安全地重复执行
3. **监控任务状态**：使用 `worker/check_redis_tasks.py` 定期检查
4. **优雅关闭**：使用 SIGTERM 而不是 kill -9
5. **多 Worker 部署**：避免所有 Worker 同时停止

---

## 总结

### 关键要点

1. **任务存储在 Redis 中**，不在 Worker 内存中
2. **Worker 停止不影响任务**，任务仍在 Redis 中
3. **新 Worker 启动时**，会自动从 Redis 读取队列中的任务
4. **Redis 是持久化的**，即使服务器重启，只要 Redis 数据还在，任务就不会丢失
5. **Worker 只是执行器**，负责从 Redis 读取任务并执行
6. **任务执行途中 Worker 被关闭，会自动重试**（前提是配置了 retry）
7. **新 Worker 启动时会自动清理僵尸任务并触发重试**

### 快速参考

- **部署**：使用 Supervisor 或 PM2 管理 Worker 进程
- **持久化**：任务信息存储在 Redis，Worker 停止不影响任务
- **重试**：配置 `retry=Retry(max=3, interval=60)` 实现自动重试
- **中断处理**：Worker 启动时自动清理僵尸任务并触发重试
- **监控**：使用 `worker/check_redis_tasks.py` 查看任务状态

