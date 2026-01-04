#!/bin/bash
# RQ Worker 启动脚本
# 用于宝塔面板 Supervisor 管理器

# 激活 Python 项目环境
source py-project-env yuekai_ophthalmology_server

# 切换到 worker 目录
cd /www/wwwroot/yuekai_ophthalmology_server/worker/

# 启动 Worker
python worker.py

