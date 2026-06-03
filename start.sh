#!/bin/bash
# Render 部署启动脚本
uvicorn app:app --host 0.0.0.0 --port ${PORT:-8001}
