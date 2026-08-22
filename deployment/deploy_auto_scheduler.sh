#!/bin/bash

# 仅部署/更新 Excel 智能排班工具，不触碰现有业务数据库。

set -euo pipefail

APP_DIR="/var/www/zeosite"
CONFIG_DIR="/var/lib/zeosite/auto-scheduler"
NGINX_CONF="/etc/nginx/sites-available/zeosite"

cd "$APP_DIR"

python3 -m venv auto_scheduler/.venv
auto_scheduler/.venv/bin/pip install --upgrade pip
auto_scheduler/.venv/bin/pip install -r auto_scheduler/requirements.txt

sudo mkdir -p "$CONFIG_DIR"
sudo chown -R "$USER":"$USER" "$CONFIG_DIR"

sudo cp deployment/nginx.conf "$NGINX_CONF"
sudo nginx -t
sudo systemctl reload nginx

pm2 delete zeosite-auto-scheduler 2>/dev/null || true
SCHEDULER_CONFIG_PATH="$CONFIG_DIR/config.json" pm2 start "./auto_scheduler/.venv/bin/python -m streamlit run auto_scheduler/app.py --server.address 127.0.0.1 --server.port 8503 --server.baseUrlPath auto-schedule --server.maxUploadSize 10 --server.headless true --server.fileWatcherType none --client.toolbarMode minimal --browser.gatherUsageStats false" --name "zeosite-auto-scheduler" --cwd "$APP_DIR" --max-memory-restart 512M
pm2 save

curl --fail --silent --show-error http://127.0.0.1:8503/auto-schedule/_stcore/health
echo
echo "智能排班生成器已启动：https://zeosite.com/auto-schedule/"
