# ServiceMate 项目架构文档

## 1. 项目概述
ServiceMate 是一个用于门店排班管理的 Web 应用程序。它允许管理人员管理门店信息、专家列表，并根据日期和专家为门店安排访问任务。项目包含一个基于 React 的单页面前端应用（SPA）和一个基于 Node.js Express 的 RESTful 后端 API。

## 2. 技术栈说明
### 前端 (service-mate/)
- **框架**: React 19 (in `service-mate/package.json`)
- **构建工具**: Vite 7
- **编程语言**: TypeScript
- **样式**: Tailwind CSS
- **图标**: Lucide React
- **状态管理**: React Hooks (useState, useMemo, useEffect, useCallback)

### 后端 (server.js)
- **框架**: Express.js (ES Module)
- **数据库**: SQLite (使用 `better-sqlite3`)
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
- **排班日历 (Calendar Tab)**: 
  - 支持月视图和周视图切换。
  - 根据选中的专家过滤排班记录。
  - 支持批量添加未安排门店。
- **数据管理 (Admin Tab)**:
  - 门店库 CRUD 操作。
  - 批量导入/更新门店信息 (基于 CSV/Excel 格式文本)。
  - 专家列表维护。
- **状态中心**:
  - 管理全局数据 (stores, experts, visits) 及其加载状态。
  - 提供全局 Toast 通知。

### 后端模块
- **API 服务 (Express)**:
  - 处理 HTTP 请求并路由到相应的数据库操作。
- **数据库访问层 (SQLite)**:
  - 使用 `better-sqlite3` 执行同步 SQL 查询。
  - 包含事务支持 (用于批量导入)。
- **数据库初始化**:
  - 在启动时检查并创建 `stores`, `experts`, `visits` 表。

## 5. 数据流架构
1. **初始化**: 前端加载时，通过 `fetchAllData` 函数并行调用 `/api/stores`, `/api/experts`, `/api/visits` 接口。
2. **交互响应**: 
   - 用户在日历上点击日期，更新 `selectedDateForVisit` 状态。
   - 用户点击“批量添加”，发送 `POST /api/visits` 请求到后端。
   - 用户在管理页导入数据，发送 `POST /api/stores/batch` 请求。
3. **数据同步**: 后端接收请求，执行 SQL 更新数据库，返回结果。前端收到成功响应后，通过 `fetchAllData` 或局部状态更新同步 UI。

## 6. 接口定义 (REST API)
| 接口名 | 方法 | 路径 | 说明 |
| :--- | :--- | :--- | :--- |
| 获取门店 | GET | `/api/stores` | 返回所有门店列表 |
| 批量更新门店 | POST | `/api/stores/batch` | 批量插入或更新门店 (Upsert) |
| 删除门店 | DELETE | `/api/stores/:id` | 删除门店及其关联排班 |
| 获取排班 | GET | `/api/visits` | 获取排班记录 (支持 `month` 参数) |
| 添加排班 | POST | `/api/visits` | 创建新的访问记录 |
| 删除排班 | DELETE | `/api/visits/:id` | 删除指定的排班记录 |
| 获取专家 | GET | `/api/experts` | 返回所有专家姓名列表 |
| 添加专家 | POST | `/api/experts` | 插入新专家姓名 |
| 删除专家 | DELETE | `/api/experts/:name` | 删除指定专家 |

## 7. 配置文件说明
- **`package.json`**: 
  - 根目录版：主要用于运行后端服务器和管理后端依赖。
  - `service-mate/` 版：用于管理前端开发、构建和 lint。
- **`vite.config.ts`**: 配置 React 插件和构建输出。
- **`tailwind.config.js`**: 定义 Tailwind CSS 的内容扫描路径和主题扩展。
- **`tsconfig.json`**: TypeScript 编译选项，定义模块解析规则。
- **`API_BASE` (in `App.tsx`)**: 动态决定 API 地址。如果是 `localhost` 则指向 `http://localhost:3000/api`，否则指向 `/schedule/api`。

## 8. 部署架构
- **前端部署**: 构建后的静态文件 (通常是 `service-mate/dist/`) 可由 Nginx 或静态托管服务部署。
- **后端部署**: 使用 PM2 或类似工具运行 `node server.js`。
- **反向代理**: 建议使用 Nginx 配置 `/api` 路径的代理转发到 Node.js 服务。

## 9. 后续迭代注意事项
- **性能优化**: 随着数据量增长，`App.tsx` 中的 `useMemo` 计算逻辑可能需要进一步优化。考虑将 `App.tsx` 拆分为更小的组件。
- **状态管理**: 随着功能复杂化，建议引入 Redux Toolkit 或 Zustand 等状态管理库，避免 `App.tsx` 过于臃肿。
- **权限管理**: 当前系统无身份验证，建议添加用户登录及不同角色的访问控制。
- **数据库迁移**: 当前使用 `db.exec` 直接初始化表，后续迭代应考虑引入数据库迁移工具 (如 Knex.js 或 Prisma)。
- **代码规范**: 当前前端代码高度集中在 `App.tsx`，建议按组件、钩子、服务层进行目录结构重构。
- **API 地址硬编码**: `API_BASE` 的硬编码逻辑应移至环境变量文件 (`.env`)。
