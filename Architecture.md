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
  - Token 默认有效期 7 天；过期或无效 Token 返回 401 并要求重新登录。
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
- `province`: TEXT
- `city`: TEXT
- `assigned_expert`: TEXT (关联 User Name)
- `monthly_frequency`: INTEGER
- `special_requirements`: TEXT
- `import_status`: TEXT (导入状态: 是/否/空)
- `deleted_at`: TEXT (停用时间；非空表示门店已停用/归档)
- `service_start_month`: TEXT (YYYY-MM，门店从该月开始纳入常规待排计算；新增门店默认=创建当月)
- `service_resume_month`: TEXT (YYYY-MM，门店恢复后从该月开始重新纳入常规待排计算；恢复门店默认=恢复当月)

### Visits (排班表)
- `id`: TEXT PRIMARY KEY
- `store_id`: TEXT
- `date`: TEXT (YYYY-MM-DD)
- `expert_name`: TEXT
- `status`: TEXT
- `type`: TEXT (`regular` 常规 / `extra` 临时)
- `title`: TEXT (临时上门原因；`extra` 必填)
- `count_towards_target`: INTEGER (0/1，是否计入当月目标次数)
- `created_by`: INTEGER (创建者 user.id)
- `created_at`: DATETIME

### Store Month Plans (门店月度计划表)
- `store_id`: TEXT
- `month`: TEXT (YYYY-MM)
- `target_frequency`: INTEGER (该月目标次数，可为 0)
- `reason`: TEXT (原因/备注)
- `updated_by`: INTEGER (更新者 user.id)
- `updated_at`: DATETIME

### Audit Logs (审计日志)
- `id`: INTEGER PRIMARY KEY
- `admin_id`: INTEGER
- `action`: TEXT
- `target_user_id`: INTEGER

## 7. 接口定义 (REST API) & 权限控制 (RBAC)

### 权限矩阵
| 功能模块 | 操作 | 路径 | 管理员 (Admin) | 普通用户 (User) |
| :--- | :--- | :--- | :--- | :--- |
| **认证** | 登录 | POST `/api/auth/login` | ✅ | ✅ |
| **账号管理** | 查看列表 | GET `/api/admin/users` | ✅ | ⛔ 403 |
| | 创建账号 | POST `/api/admin/users` | ✅ | ⛔ 403 |
| | 更新账号 | PUT `/api/admin/users/:id` | ✅ | ⛔ 403 |
| **门店管理** | 查看列表 | GET `/api/stores` | ✅ | ✅ |
| | 单个更新 | PUT `/api/stores/:id` | ✅ (所有字段) | ⚠️ (仅限频次/专家/需求) |
| | 批量导入 | POST `/api/stores/batch` | ✅ | ⛔ 403 |
| | 停用门店 | DELETE `/api/stores/:id` | ✅ | ⛔ 403 |
| | 恢复门店 | POST `/api/stores/:id/restore` | ✅ | ⛔ 403 |
| **月度计划** | 获取某月计划 | GET `/api/store-month-plans?month=YYYY-MM` | ✅ | ✅ |
| | 设置本月计划 | PUT `/api/stores/:id/month-plan` | ✅ | ⛔ 403 |
| | 清除本月计划 | DELETE `/api/stores/:id/month-plan?month=YYYY-MM` | ✅ | ⛔ 403 |
| **排班管理** | 查看排班 | GET `/api/visits` | ✅ | ✅ |
| | 添加排班 | POST `/api/visits` | ✅ | ✅ (仅允许创建 expert_name=本人) |
| | 更新排班 | PUT `/api/visits/:id` | ✅ | ✅ (仅允许更新本人排班) |
| | 删除排班 | DELETE `/api/visits/:id` | ✅ | ✅ (仅允许删除本人排班) |

### 字段级权限 (PUT /api/stores/:id)
- **管理员**: 可编辑 `name`, `brand`, `city`, `assignedExpert`, `monthlyFrequency`, `specialRequirements`, `importStatus`。
- **普通用户**: 仅可编辑 `assignedExpert` (负责专家), `monthlyFrequency` (服务频次)。其他字段若提交将被忽略。

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
| 更新门店 | PUT | `/api/stores/:id` | User/Admin | 单个更新门店 (User 仅限部分字段) |
| 批量更新门店 | POST | `/api/stores/batch` | Admin | 批量插入或更新门店 (8列数据，含导入状态) |
| 停用门店 | DELETE | `/api/stores/:id` | Admin | 停用门店；存在未来 planned 时阻止停用 |
| 恢复门店 | POST | `/api/stores/:id/restore` | Admin | 恢复已停用门店 |
| 获取门店月度计划 | GET | `/api/store-month-plans?month=YYYY-MM` | User/Admin | 获取某月所有门店目标次数覆盖 |
| 设置门店月度计划 | PUT | `/api/stores/:id/month-plan` | Admin | 设置指定门店在某月的目标次数 |
| 清除门店月度计划 | DELETE | `/api/stores/:id/month-plan?month=YYYY-MM` | Admin | 清除指定门店在某月的目标次数覆盖 |
| 获取排班 | GET | `/api/visits` | User/Admin | 获取排班记录 |
| 添加排班 | POST | `/api/visits` | User/Admin | 创建新的访问记录 |
| 更新排班 | PUT | `/api/visits/:id` | User/Admin | 更新日期/状态/原因/计入规则（User 仅限本人） |
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
