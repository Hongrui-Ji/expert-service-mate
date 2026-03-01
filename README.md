# 专家排班管理系统 (Expert Service Mate)

这是一个基于 React + Node.js + SQLite 的全栈专家排班与门店管理系统。

## 🚀 快速开始

### 1. 启动后端服务
后端服务运行在 3000 端口，负责 API 接口和数据库交互。

```bash
# 在项目根目录下
npm install
node server.js
```

### 2. 启动前端服务
前端服务运行在 5173 端口 (默认)，提供用户界面。

```bash
# 进入前端目录
cd service-mate
npm install
npm run dev
```

访问地址: http://localhost:5173/schedule/

---

## 🛠 GitHub 维护指南

恭喜您已成功将项目上传至 GitHub！在后续的开发过程中，您将主要使用以下流程来维护代码。

### 1. 日常开发流程 (最常用)

每次您完成一个功能开发或修复一个 Bug 后，请执行以下三个标准步骤：

**第一步：查看状态**
查看哪些文件发生了变化。
```bash
git status
```

**第二步：添加更改**
将所有修改过的文件加入暂存区。
```bash
git add .
```

**第三步：提交更改**
将暂存区的修改保存为一次“提交”，并附上说明信息。
```bash
git commit -m "描述您做了什么修改，例如：修复了登录页面的样式问题"
```

**第四步：推送到 GitHub**
将本地的提交同步到远程 GitHub 仓库。
```bash
git push
```

### 2. 多人协作或多设备同步

如果您在另一台电脑上更新了代码，或者有其他人修改了代码，您需要先将最新的代码“拉取”到本地：

```bash
git pull
```
*建议在每天开始工作前，先执行一次 `git pull`。*

### 3. 分支管理 (进阶)

如果您要开发一个比较大、风险较高的新功能，建议使用分支，以免影响主程序的稳定性。

```bash
# 创建并切换到新分支
git checkout -b feature-new-login

# ... 进行开发、add、commit ...

# 切回主分支
git checkout main

# 将新功能合并回主分支
git merge feature-new-login
```

## 📂 项目结构

- `/server.js` - 后端入口文件，包含数据库定义和 API 接口。
- `/service-mate/` - 前端 React 项目目录。
- `/database.sqlite` - SQLite 数据库文件 (由 server.js 自动生成)。
- `/Deployment.md` - 详细部署文档。
- `/Architecture.md` - 系统架构文档。
