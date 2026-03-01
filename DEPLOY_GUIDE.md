# ZeoSite 部署指南

本指南将帮助你将 ZeoSite Workspace 部署到 Ubuntu 24.04 服务器。

**服务器信息**:
- IP: `43.154.131.84`
- 域名: `zeosite.com`
- 部署目录: `/var/www/zeosite`

---

## 第一步：登录服务器

使用 SSH 连接到你的服务器（请确保你有 root 权限或 sudo 权限）：
```bash
ssh root@43.154.131.84
# 输入密码
```

## 第二步：准备环境

如果你是**首次**在这台服务器上部署 Node.js 应用，请执行以下命令来安装必要软件（Node.js, NPM, PM2, Nginx）：

```bash
# 更新系统并安装基础工具
sudo apt update && sudo apt install -y curl git nginx build-essential

# 安装 Node.js v20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 安装 PM2 (进程管理器)
sudo npm install -g pm2

# 启动 Nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

## 第三步：部署代码

假设你的代码已上传至 GitHub（例如 `https://github.com/yourusername/expert-workspace.git`）。

1. **清理旧数据** (根据需求，你提到旧数据可以删除)：
   ```bash
   sudo rm -rf /var/www/zeosite
   ```

2. **拉取新代码**：
   ```bash
   sudo git clone https://github.com/Hongrui-Ji/expert-service-mate /var/www/zeosite
   
   
   # 如果是私有仓库，可能需要配置 SSH Key 或输入账号密码
   ```

3. **进入项目目录**：
   ```bash
   cd /var/www/zeosite
   ```

4. **安装依赖并构建**：
   ```bash
   # 安装后端依赖
   npm install

   # 安装前端依赖并构建
   cd service-mate
   npm install
   npm run build
   cd ..
   ```

## 第四步：配置 Nginx

我们需要配置 Nginx 将 `zeosite.com` 的流量转发到本地 Node 服务（端口 3000）。

1. **创建配置文件**：
   ```bash
   sudo nano /etc/nginx/sites-available/zeosite
   ```

2. **粘贴以下内容**：
   ```nginx
   server {
       listen 80;
       server_name zeosite.com www.zeosite.com;

       location / {
           proxy_pass http://localhost:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       }
   }
   ```

3. **启用配置并重启 Nginx**：
   ```bash
   sudo ln -sf /etc/nginx/sites-available/zeosite /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default  # 如果这是唯一的站点，建议移除默认配置
   sudo nginx -t
   sudo systemctl reload nginx
   ```

## 第五步：启动应用

使用 PM2 启动 Node.js 服务，确保它在后台稳定运行。

```bash
# 在 /var/www/zeosite 目录下
pm2 start server.js --name "zeosite-api"

# 保存当前进程列表，以便开机自启
pm2 save
pm2 startup
```

## 第六步：验证

打开浏览器访问 [http://zeosite.com](http://zeosite.com)。
- 根路径 `/` 应显示 "欢迎来到 Neo 的网站"。
- `/workspace` 应显示工作台。
- `/workspace/schedule` 应进入排班系统。

---

## 后续更新部署

当你推送了新代码到 GitHub 后，在服务器上只需执行：

```bash
cd /var/www/zeosite
git pull
npm install  # 如果依赖有变更
cd service-mate && npm install && npm run build && cd ..
pm2 restart zeosite-api
```
