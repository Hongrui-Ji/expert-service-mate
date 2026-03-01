# ServiceMate 项目架构文档

## 1. 项目概述
ServiceMate 是一个用于门店排班管理的 Web 应用程序。它允许管理人员管理门店信息、专家列表，并根据日期和专家为门店安排访问任务。项目包含一个基于 React 的单页面前端应用（SPA）和一个基于 Node.js Express 的 RESTful 后端 API。

## 2. 技术栈说明
### 前端 (service-mate/)
- **框架**: React 19
- **构建工具**: Vite 7
- **编程语言**: TypeScript
- **样式**: Tailwind CSS
- **图标**: Lucide React
- **状态管理**: React Hooks (useState, useMemo, useEffect, useCallback)

### 后端 (server.js)
- **框架**: Express.js (ES Module)
- **数据库**: SQLite (使用 `better-sqlite3`)
- **认证**: JWT (JSON Web Tokens) + bcryptjs (密码哈希)
- **跨域**: CORS

### 基础设施
- **开发环境**: Node.js, npm
- **生产环境 (预测)**: Nginx (作为反向代理和静态资源服务)

## 3. 目录结构
```text
/
├── service-mate/           # 前端源代码
│   ├── src/
│   │   ├── App.tsx         # 核心应用逻辑
│   │   ├── main.tsx        # 应用入口点
│   │   └── index.css       # 全局样式
│   ├── public/             # 静态公共资源
│   ├── vite.config.ts      # Vite 配置文件
│   ├── tailwind.config.js  # Tailwind 配置文件
│   └── package.json        # 前端依赖与脚本
├── landing_page/           # 静态着陆页
├── server.js               # 后端 API 服务器
├── database.sqlite         # SQLite 数据库文件 (运行时生成)
├── package.json            # 根目录依赖与脚本 (包含后端依赖)
└── README.md               # 项目说明
```

## 4. 核心模块设计
### 前端模块
- **认证模块 (Login)**:
  - 手机号 + 密码登录。
  - JWT Token 存储与请求拦截。
- **排班日历 (Calendar Tab)**: 
  - 支持月视图和周视图切换。
  - 必须选择特定专家查看其排班记录（不再支持“全部专家”视图）。
  - 支持批量添加未安排门店。
- **数据管理 (Admin Tab)**:
  - **账号管理**: 管理员可创建/编辑/禁用用户账号 (专家)。
  - **门店管理**: 门店库 CRUD 操作。
  - **批量导入**: 支持 Excel/CSV 文本粘贴导入门店信息 (自动解析 Tab/空格/逗号分隔符)。
- **状态中心**:
  - 管理全局数据 (stores, visits) 及其加载状态。
  - 提供全局 Toast 通知。

### 后端模块
- **API 服务 (Express)**:
  - 处理 HTTP 请求并路由到相应的数据库操作。
  - **中间件**: `authenticateToken` (验证 JWT), `isAdmin` (验证管理员权限)。
- **数据库访问层 (SQLite)**:
  - 使用 `better-sqlite3` 执行同步 SQL 查询。
  - 包含事务支持 (用于批量导入)。
- **数据库初始化**:
  - 在启动时检查并创建 `users`, `roles`, `stores`, `visits`, `audit_logs` 表。
  - 自动创建默认管理员账号 (Admin@123)。

## 5. 数据流架构
1. **初始化**: 前端加载时，通过 `fetchAllData` 函数并行调用 `/api/stores`, `/api/experts` (即 users), `/api/visits` 接口。
2. **交互响应**: 
   - 用户登录后获取 JWT Token，后续请求自动携带 Bearer Token。
   - 管理员在“账号管理”中创建用户，后端写入 `users` 表。
   - 用户在管理页导入数据，发送 `POST /api/stores/batch` 请求。
3. **数据同步**: 后端接收请求，执行 SQL 更新数据库，返回结果。前端收到成功响应后，通过 `fetchAllData` 或局部状态更新同步 UI。

## 6. 数据库设计 (Schema)
### Users (用户/专家表)
- `id`: INTEGER PRIMARY KEY
- `name`: TEXT (姓名)
- `phone`: TEXT UNIQUE (手机号)
- `password_hash`: TEXT (加密密码)
- `role_id`: INTEGER (关联 Roles 表)
- `status`: INTEGER (1:正常, 0:禁用)

### Roles (角色表)
- `id`: INTEGER PRIMARY KEY
- `name`: TEXT (admin/user)

### Stores (门店表)
- `id`: TEXT PRIMARY KEY
- `name`: TEXT
- `brand`: TEXT
- `city`: TEXT (原 Province 字段已移除)
- `assigned_expert`: TEXT (关联 User Name)
- `monthly_frequency`: INTEGER
- `special_requirements`: TEXT

### Visits (排班表)
- `id`: TEXT PRIMARY KEY
- `store_id`: TEXT
- `date`: TEXT (YYYY-MM-DD)
- `expert_name`: TEXT
- `status`: TEXT

### Audit Logs (审计日志)
- `id`: INTEGER PRIMARY KEY
- `admin_id`: INTEGER
- `action`: TEXT
- `target_user_id`: INTEGER

## 7. 接口定义 (REST API)

### 认证 (Auth)
| 接口名 | 方法 | 路径 | 权限 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 用户登录 | POST | `/api/auth/login` | 公开 | 返回 JWT Token |

### 管理员 (Admin)
| 接口名 | 方法 | 路径 | 权限 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 获取用户列表 | GET | `/api/admin/users` | Admin | 获取所有账号信息 |
| 创建账号 | POST | `/api/admin/users` | Admin | 创建新专家/管理员 |
| 更新账号 | PUT | `/api/admin/users/:id` | Admin | 修改信息或重置密码 |

### 业务数据 (Business)
| 接口名 | 方法 | 路径 | 权限 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 获取门店 | GET | `/api/stores` | User/Admin | 返回所有门店列表 |
| 批量更新门店 | POST | `/api/stores/batch` | Admin | 批量插入或更新门店 (7列数据) |
| 删除门店 | DELETE | `/api/stores/:id` | Admin | 删除门店及其关联排班 |
| 获取排班 | GET | `/api/visits` | User/Admin | 获取排班记录 |
| 添加排班 | POST | `/api/visits` | User/Admin | 创建新的访问记录 |
| 删除排班 | DELETE | `/api/visits/:id` | User/Admin | 删除指定的排班记录 |
| 获取专家列表 | GET | `/api/experts` | User/Admin | 返回所有有效用户的姓名列表 |

## 8. 部署架构
- **前端部署**: 构建后的静态文件 (通常是 `service-mate/dist/`) 可由 Nginx 或静态托管服务部署。
- **后端部署**: 使用 PM2 或类似工具运行 `node server.js`。
- **反向代理**: 建议使用 Nginx 配置 `/api` 路径的代理转发到 Node.js 服务。

## 9. 后续迭代注意事项
- **性能优化**: 随着数据量增长，`App.tsx` 中的 `useMemo` 计算逻辑可能需要进一步优化。考虑将 `App.tsx` 拆分为更小的组件。
- **数据库迁移**: 当前使用 `db.exec` 直接初始化表，后续迭代应考虑引入数据库迁移工具 (如 Knex.js 或 Prisma)。
- **代码规范**: 当前前端代码高度集中在 `App.tsx`，建议按组件、钩子、服务层进行目录结构重构。
- **API 地址硬编码**: `API_BASE` 的硬编码逻辑应移至环境变量文件 (`.env`)。
