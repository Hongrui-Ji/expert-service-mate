#!/bin/bash

# 服务器初始化脚本
# 仅需运行一次

set -e

echo "开始安装系统依赖..."
sudo apt update
sudo apt install -y curl git nginx build-essential python3 python3-venv python3-pip

# 安装 Node.js (v20)
echo "安装 Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 安装 PM2
echo "安装 PM2..."
sudo npm install -g pm2

# 启动 Nginx
echo "配置 Nginx..."
sudo systemctl enable nginx
sudo systemctl start nginx

echo "环境安装完成！请继续执行 deploy.sh 部署代码。"
