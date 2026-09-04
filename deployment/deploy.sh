#!/bin/bash

# 部署脚本
# 用法: ./deploy.sh [GITHUB_REPO_URL]
# 示例: ./deploy.sh https://github.com/yourname/expert_workspace.git

REPO_URL=$1
APP_DIR="/var/www/zeosite"
NGINX_CONF="/etc/nginx/sites-available/zeosite"

if [ -z "$REPO_URL" ]; then
  echo "请提供 GitHub 仓库地址作为参数！"
  echo "用法: ./deploy.sh <YOUR_GITHUB_REPO_URL>"
  exit 1
fi

echo "=== 开始部署 ZeoSite Workspace ==="

# 1. 清理旧目录 (可选，如果确认不需要保留数据)
# 注意：如果 database.sqlite 需要保留，请先备份
if [ -d "$APP_DIR" ]; then
    echo "备份旧数据..."
    cp "$APP_DIR/database.sqlite" /tmp/database.sqlite.bak 2>/dev/null || echo "无旧数据库需备份"
    
    echo "清理旧目录..."
    sudo rm -rf "$APP_DIR"
fi

# 2. 拉取代码
echo "拉取代码..."
sudo git clone "$REPO_URL" "$APP_DIR"
sudo chown -R $USER:$USER "$APP_DIR"

# 3. 恢复数据 (如果存在备份)
if [ -f "/tmp/database.sqlite.bak" ]; then
    echo "恢复数据库..."
    mv /tmp/database.sqlite.bak "$APP_DIR/database.sqlite"
fi

cd "$APP_DIR"

# 4. 安装依赖
echo "安装后端依赖..."
npm install

echo "构建前端项目..."
cd service-mate
npm install
npm run build
cd ..

echo "部署终端监测报告工具 (Streamlit)..."
cd reporttowuye
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
sudo ./.venv/bin/python -m playwright install-deps chromium
./.venv/bin/python -m playwright install chromium
cd ..

echo "部署智能排班生成器 (Streamlit)..."
cd auto_scheduler
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
cd ..

echo "准备智能排班共享配置目录..."
sudo mkdir -p /var/lib/zeosite/auto-scheduler
sudo chown -R $USER:$USER /var/lib/zeosite/auto-scheduler

echo "准备终端报告登录态目录..."
sudo mkdir -p /var/lib/zeosite/terminal-report
sudo chown -R $USER:$USER /var/lib/zeosite/terminal-report
chmod 700 /var/lib/zeosite/terminal-report

# 5. 配置 Nginx
echo "配置 Nginx..."
sudo cp deployment/nginx.conf "$NGINX_CONF"
sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 6. 启动服务 (PM2)
echo "启动 Node 服务..."
pm2 delete zeosite-api 2>/dev/null || true
pm2 start server.js --name "zeosite-api"

echo "启动终端监测报告服务..."
pm2 delete zeosite-terminal-report 2>/dev/null || true
TERMINAL_REPORT_ENV_FILE="/var/lib/zeosite/terminal-report/config.env"
if [ -f "$TERMINAL_REPORT_ENV_FILE" ]; then
    set -a
    source "$TERMINAL_REPORT_ENV_FILE"
    set +a
else
    echo "警告：未找到 $TERMINAL_REPORT_ENV_FILE，自动获取图片功能将暂不可用"
fi
export YANSHOU_STATE_PATH="/var/lib/zeosite/terminal-report/yanshou-storage-state.json"
pm2 start "./.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.baseUrlPath workspace/terminal-report --server.maxUploadSize 10 --server.headless true --browser.gatherUsageStats false" --name "zeosite-terminal-report" --cwd "$APP_DIR/reporttowuye"

echo "启动现场作业报告服务..."
pm2 delete zeosite-onsite-report 2>/dev/null || true
pm2 start "./.venv/bin/python -m streamlit run pco_onsite_report_app.py --server.address 127.0.0.1 --server.port 8502 --server.baseUrlPath onsite-report --server.maxUploadSize 10 --server.headless true" --name "zeosite-onsite-report" --cwd "$APP_DIR/reporttowuye"

echo "启动智能排班生成器..."
pm2 delete zeosite-auto-scheduler 2>/dev/null || true
SCHEDULER_CONFIG_PATH=/var/lib/zeosite/auto-scheduler/config.json pm2 start "./auto_scheduler/.venv/bin/python -m streamlit run auto_scheduler/app.py --server.address 127.0.0.1 --server.port 8503 --server.baseUrlPath auto-schedule --server.maxUploadSize 10 --server.headless true --server.fileWatcherType none --client.toolbarMode minimal --browser.gatherUsageStats false" --name "zeosite-auto-scheduler" --cwd "$APP_DIR" --max-memory-restart 512M
pm2 save

echo "=== 部署完成！ ==="
echo "访问地址: http://zeosite.com"
echo "现场作业报告: http://zeosite.com/onsite-report/"
echo "智能排班生成器: http://zeosite.com/auto-schedule/"
