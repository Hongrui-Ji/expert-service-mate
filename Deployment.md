# ServiceMate 部署与迁移文档 (Ubuntu)

## 1. 环境要求
- **操作系统**: Ubuntu 20.04 LTS 或更高版本
- **运行时**: Node.js 18.x +
- **进程管理**: PM2 (推荐)
- **数据库**: SQLite 3

## 2. 数据库设计 (Schema)
系统采用基于角色的访问控制 (RBAC) 的基础架构：

### 用户表 (`users`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | INTEGER (PK) | 用户唯一标识 |
| username | TEXT (Unique) | 登录用户名 |
| phone | TEXT | 电话号码 |
| email | TEXT (Unique) | 电子邮箱 |
| password_hash | TEXT | Bcrypt 加密后的密码 |
| role_id | INTEGER (FK) | 关联角色 ID |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 角色表 (`roles`)
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| id | INTEGER (PK) | 角色 ID |
| name | TEXT (Unique) | 角色名称 (`admin`, `user`) |
| description | TEXT | 角色描述 |

## 3. 部署步骤

### 第一步：安装依赖
在服务器上克隆代码后，执行：
```bash
# 安装后端依赖
npm install

# 安装前端依赖并构建
cd service-mate
npm install
npm run build
```

### 第二步：数据库迁移
运行以下脚本初始化数据库结构（包含预置角色）：
```bash
node -e "
const Database = require('better-sqlite3');
const db = new Database('database.sqlite');
db.exec(\`
  CREATE TABLE IF NOT EXISTS roles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, description TEXT);
  CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, phone TEXT, email TEXT UNIQUE, password_hash TEXT NOT NULL, role_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(role_id) REFERENCES roles(id));
  CREATE TABLE IF NOT EXISTS stores (id TEXT PRIMARY KEY, name TEXT NOT NULL, brand TEXT, city TEXT, assigned_expert TEXT, special_requirements TEXT, monthly_frequency INTEGER DEFAULT 1);
  CREATE TABLE IF NOT EXISTS experts (name TEXT PRIMARY KEY);
  CREATE TABLE IF NOT EXISTS visits (id TEXT PRIMARY KEY, store_id TEXT, date TEXT, expert_name TEXT, status TEXT DEFAULT 'planned', FOREIGN KEY(store_id) REFERENCES stores(id));
\`);
const initRoles = db.prepare('INSERT OR IGNORE INTO roles (name, description) VALUES (?, ?)');
initRoles.run('admin', 'Administrator');
initRoles.run('user', 'Standard User');
console.log('Database migrated successfully.');
"
```

### 第三步：配置环境变量
在服务器上设置必要的环境变量（或修改 `server.js` 中的配置）：
- `JWT_SECRET`: 随机长字符串
- `PORT`: 默认 3000

### 第四步：启动服务
使用 PM2 启动后端：
```bash
pm2 start server.js --name service-mate-api
```

## 4. 安全性说明
- **密码安全**: 使用 Bcrypt 进行 10 轮哈希加密。
- **接口保护**: 核心业务 API 均通过 `authenticateToken` 中间件验证 JWT。
- **注入防护**: 数据库操作全部使用 `better-sqlite3` 的预处理语句 (Prepared Statements)。
