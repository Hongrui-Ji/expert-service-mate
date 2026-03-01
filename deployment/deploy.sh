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

# 5. 配置 Nginx
echo "配置 Nginx..."
sudo cp deployment/nginx.conf "$NGINX_CONF"
sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 6. 启动服务 (PM2)
echo "启动 Node 服务..."
pm2 delete zeosite-api 2>/dev/null || true
pm2 start server.js --name "zeosite-api"
pm2 save

echo "=== 部署完成！ ==="
echo "访问地址: http://zeosite.com"
