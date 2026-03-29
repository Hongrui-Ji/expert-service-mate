import express from 'express';
import Database from 'better-sqlite3';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';

// --- ES Module 兼容性处理 ---
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// 配置
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key-12345'; // 生产环境应从环境变量获取
const PORT = 3000;
const DB_PATH = path.join(__dirname, 'database.sqlite');

// 校验正则表达式
const PHONE_REGEX = /^1[3-9]\d{9}$/;
const PASSWORD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/; // 至少8位，含大小写字母+数字

// 初始化应用
const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// 初始化数据库
const db = new Database(DB_PATH);
db.pragma('foreign_keys = ON');

const formatLocalDate = (d = new Date()) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

const formatLocalMonth = (d = new Date()) => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
};

// 建表逻辑 (完全重构权限与账号系统)
db.exec(`
  CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT
  );

  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    status INTEGER DEFAULT 1, -- 1: 正常, 0: 禁用
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(role_id) REFERENCES roles(id)
  );

  CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER,
    action TEXT NOT NULL,
    target_user_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS stores (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    brand TEXT,
    province TEXT,
    city TEXT,
    assigned_expert TEXT,
    monthly_frequency INTEGER DEFAULT 1,
    special_requirements TEXT,
    deleted_at TEXT,
    service_start_month TEXT,
    service_resume_month TEXT
  );

  CREATE TABLE IF NOT EXISTS experts (
    name TEXT PRIMARY KEY
  );

  CREATE TABLE IF NOT EXISTS visits (
    id TEXT PRIMARY KEY,
    store_id TEXT,
    date TEXT,
    expert_name TEXT,
    status TEXT DEFAULT 'planned',
    type TEXT DEFAULT 'regular',
    title TEXT,
    count_towards_target INTEGER DEFAULT 1,
    created_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(store_id) REFERENCES stores(id)
  );

  CREATE TABLE IF NOT EXISTS store_month_plans (
    store_id TEXT NOT NULL,
    month TEXT NOT NULL,
    target_frequency INTEGER NOT NULL,
    reason TEXT,
    updated_by INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(store_id, month),
    FOREIGN KEY(store_id) REFERENCES stores(id)
  );
`);

// 数据库迁移：添加 import_status 字段
try {
  db.prepare("ALTER TABLE stores ADD COLUMN import_status TEXT").run();
  console.log("Migration: Added import_status column to stores table.");
} catch (e) {
  // Column likely already exists
}

try {
  db.prepare("ALTER TABLE stores ADD COLUMN province TEXT").run();
  console.log("Migration: Added province column to stores table.");
} catch (e) {
  // Column likely already exists
}

try {
  db.prepare("ALTER TABLE stores ADD COLUMN deleted_at TEXT").run();
  console.log("Migration: Added deleted_at column to stores table.");
} catch (e) {
  // Column likely already exists
}

try {
  db.prepare("ALTER TABLE stores ADD COLUMN service_start_month TEXT").run();
  console.log("Migration: Added service_start_month column to stores table.");
} catch (e) {
  // Column likely already exists
}

try {
  db.prepare("ALTER TABLE stores ADD COLUMN service_resume_month TEXT").run();
  console.log("Migration: Added service_resume_month column to stores table.");
} catch (e) {
  // Column likely already exists
}

try {
  db.prepare("ALTER TABLE visits ADD COLUMN type TEXT").run();
  console.log("Migration: Added type column to visits table.");
} catch (e) {}

try {
  db.prepare("ALTER TABLE visits ADD COLUMN title TEXT").run();
  console.log("Migration: Added title column to visits table.");
} catch (e) {}

try {
  db.prepare("ALTER TABLE visits ADD COLUMN count_towards_target INTEGER").run();
  console.log("Migration: Added count_towards_target column to visits table.");
} catch (e) {}

try {
  db.prepare("ALTER TABLE visits ADD COLUMN created_by INTEGER").run();
  console.log("Migration: Added created_by column to visits table.");
} catch (e) {}

try {
  db.prepare("ALTER TABLE visits ADD COLUMN created_at DATETIME").run();
  console.log("Migration: Added created_at column to visits table.");
} catch (e) {}

try {
  db.prepare("UPDATE visits SET type = 'regular' WHERE type IS NULL").run();
} catch (e) {}

try {
  db.prepare("UPDATE visits SET count_towards_target = 1 WHERE count_towards_target IS NULL").run();
} catch (e) {}

// 预制角色与管理员账号
const initRoles = db.prepare("INSERT OR IGNORE INTO roles (name, description) VALUES (?, ?)");
initRoles.run('admin', '超级管理员');
initRoles.run('user', '普通专家');

// 检查是否已有管理员，若无则创建一个默认的
const adminCount = db.prepare("SELECT COUNT(*) as count FROM users WHERE role_id = (SELECT id FROM roles WHERE name = 'admin')").get();
if (adminCount.count === 0) {
  const adminPassword = 'Admin@123'; 
  const passwordHash = bcrypt.hashSync(adminPassword, 10);
  const adminRole = db.prepare("SELECT id FROM roles WHERE name = 'admin'").get();
  db.prepare('INSERT INTO users (name, phone, password_hash, role_id) VALUES (?, ?, ?, ?)').run(
    '超级管理员', '13800138000', passwordHash, adminRole.id
  );
  console.log('--- DEFAULT ADMIN CREATED ---');
  console.log('Name: 超级管理员');
  console.log('Phone: 13800138000');
  console.log('Password: Admin@123');
  console.log('----------------------------');
}

// 预制默认专家数据 - 已废弃，使用 users 表管理
// const initExperts = db.prepare("INSERT OR IGNORE INTO experts (name) VALUES (?)");
// ['张三', '李四', '王五', '赵六'].forEach(name => initExperts.run(name));

// --- 认证与鉴权中间件 ---
const authenticateToken = (req, res, next) => {
  const authHeader = req.headers['authorization'];
  const token = authHeader && authHeader.split(' ')[1];
  if (!token) return res.sendStatus(401);

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) return res.sendStatus(401);
    
    // 检查用户是否在数据库中且未被禁用
    const dbUser = db.prepare('SELECT status FROM users WHERE id = ?').get(user.id);
    if (!dbUser || dbUser.status === 0) return res.status(403).json({ error: 'Account disabled' });
    
    req.user = user;
    next();
  });
};

const isAdmin = (req, res, next) => {
  if (req.user.role !== 'admin') return res.status(403).json({ error: 'Admin access required' });
  next();
};

// --- Auth API ---

// 1. 登录 (通过手机号登录)
app.post('/api/auth/login', async (req, res) => {
  const { phone, password } = req.body;
  
  if (!phone || !password) return res.status(400).json({ error: 'Missing phone or password' });

  const user = db.prepare(`
    SELECT u.*, r.name as role 
    FROM users u 
    JOIN roles r ON u.role_id = r.id 
    WHERE u.phone = ?
  `).get(phone);

  if (!user || user.status === 0) {
    return res.status(401).json({ error: '账号不存在或已被禁用' });
  }

  const validPassword = await bcrypt.compare(password, user.password_hash);
  if (!validPassword) {
    return res.status(401).json({ error: '手机号或密码错误' });
  }

  const token = jwt.sign(
    { id: user.id, name: user.name, phone: user.phone, role: user.role },
    JWT_SECRET,
    { expiresIn: '7d' }
  );

  res.json({ 
    token, 
    user: { id: user.id, name: user.name, role: user.role, phone: user.phone } 
  });
});

// --- 管理员专用 API ---

// 2. 获取用户列表
app.get('/api/admin/users', authenticateToken, isAdmin, (req, res) => {
  const users = db.prepare(`
    SELECT u.id, u.name, u.phone, u.status, u.created_at, r.name as role
    FROM users u
    JOIN roles r ON u.role_id = r.id
    ORDER BY u.created_at DESC
  `).all();
  res.json(users);
});

// 3. 管理员创建账号
app.post('/api/admin/users', authenticateToken, isAdmin, async (req, res) => {
  const { name, phone, password, role = 'user' } = req.body;
  
  // 校验
  if (!name || name.length < 2 || name.length > 20) return res.status(400).json({ error: '姓名长度需在2-20字符之间' });
  if (!PHONE_REGEX.test(phone)) return res.status(400).json({ error: '手机号格式不正确' });
  if (!PASSWORD_REGEX.test(password)) return res.status(400).json({ error: '密码需8位以上，包含大小写字母和数字' });

  // 验证专家列表关联 - 已废弃
  // const expertExists = db.prepare('SELECT 1 FROM experts WHERE name = ?').get(name);
  // if (!expertExists) {
  //   return res.status(400).json({ error: `用户姓名 "${name}" 不在专家列表中，请先添加专家` });
  // }

  try {
    const passwordHash = await bcrypt.hash(password, 10);
    const roleRow = db.prepare('SELECT id FROM roles WHERE name = ?').get(role);
    if (!roleRow) return res.status(400).json({ error: '无效的角色' });

    const result = db.prepare(`
      INSERT INTO users (name, phone, password_hash, role_id)
      VALUES (?, ?, ?, ?)
    `).run(name, phone, passwordHash, roleRow.id);

    // 记录日志
    db.prepare('INSERT INTO audit_logs (admin_id, action, target_user_id) VALUES (?, ?, ?)').run(
      req.user.id, 'CREATE_USER', result.lastInsertRowid
    );

    res.json({ success: true, userId: result.lastInsertRowid });
  } catch (err) {
    res.status(400).json({ error: '手机号已被占用' });
  }
});

// 4. 编辑/禁用账号
app.put('/api/admin/users/:id', authenticateToken, isAdmin, async (req, res) => {
  const { id } = req.params;
  const { name, phone, status, password, role } = req.body;

  try {
    const user = db.prepare('SELECT * FROM users WHERE id = ?').get(id);
    if (!user) return res.status(404).json({ error: '用户不存在' });

    let updateSql = 'UPDATE users SET updated_at = CURRENT_TIMESTAMP';
    const params = [];

    if (name) {
      if (name.length < 2 || name.length > 20) return res.status(400).json({ error: '姓名长度需在2-20字符之间' });
      updateSql += ', name = ?';
      params.push(name);
    }
    if (phone) {
      if (!PHONE_REGEX.test(phone)) return res.status(400).json({ error: '手机号格式不正确' });
      updateSql += ', phone = ?';
      params.push(phone);
    }
    if (status !== undefined) {
      updateSql += ', status = ?';
      params.push(status);
    }
    if (role) {
      const roleRow = db.prepare('SELECT id FROM roles WHERE name = ?').get(role);
      if (!roleRow) return res.status(400).json({ error: '无效的角色' });
      updateSql += ', role_id = ?';
      params.push(roleRow.id);
    }
    if (password) {
      if (!PASSWORD_REGEX.test(password)) return res.status(400).json({ error: '密码需8位以上，包含大小写字母和数字' });
      const passwordHash = await bcrypt.hash(password, 10);
      updateSql += ', password_hash = ?';
      params.push(passwordHash);
    }

    updateSql += ' WHERE id = ?';
    params.push(id);

    db.prepare(updateSql).run(...params);
    
    // 记录日志
    db.prepare('INSERT INTO audit_logs (admin_id, action, target_user_id) VALUES (?, ?, ?)').run(
      req.user.id, 'UPDATE_USER', id
    );

    res.json({ success: true });
  } catch (err) {
    res.status(400).json({ error: '更新失败，手机号可能重复' });
  }
});

// 5. 获取审计日志
app.get('/api/admin/logs', authenticateToken, isAdmin, (req, res) => {
  const logs = db.prepare(`
    SELECT l.*, u1.name as admin_name, u2.name as target_name
    FROM audit_logs l
    LEFT JOIN users u1 ON l.admin_id = u1.id
    LEFT JOIN users u2 ON l.target_user_id = u2.id
    ORDER BY l.timestamp DESC
    LIMIT 100
  `).all();
  res.json(logs);
});

// --- 原有业务 API (保持认证保护) ---

app.get('/api/stores', authenticateToken, (req, res) => {
  const stmt = db.prepare('SELECT * FROM stores');
  const stores = stmt.all().map(s => ({
    id: s.id, 
    name: s.name, 
    brand: s.brand, 
    province: s.province || '',
    city: s.city,
    assignedExpert: s.assigned_expert, 
    specialRequirements: s.special_requirements, 
    monthlyFrequency: s.monthly_frequency || 1,
    importStatus: s.import_status,
    deletedAt: s.deleted_at,
    serviceStartMonth: s.service_start_month,
    serviceResumeMonth: s.service_resume_month
  }));
  res.json(stores);
});

app.get('/api/store-month-plans', authenticateToken, (req, res) => {
  const month = String(req.query.month || '');
  if (!month) return res.status(400).json({ error: 'Missing month' });
  const rows = db.prepare('SELECT * FROM store_month_plans WHERE month = ?').all(month);
  res.json(rows.map(r => ({
    storeId: r.store_id,
    month: r.month,
    targetFrequency: r.target_frequency,
    reason: r.reason || '',
    updatedBy: r.updated_by || null,
    updatedAt: r.updated_at || null
  })));
});

app.put('/api/stores/:id/month-plan', authenticateToken, isAdmin, (req, res) => {
  const storeId = req.params.id;
  const { month, targetFrequency, reason } = req.body || {};
  if (!month || targetFrequency === undefined || targetFrequency === null) {
    return res.status(400).json({ error: 'Missing month or targetFrequency' });
  }
  const target = Number(targetFrequency);
  if (!Number.isFinite(target) || target < 0) return res.status(400).json({ error: 'Invalid targetFrequency' });
  const existingStore = db.prepare('SELECT id FROM stores WHERE id = ?').get(storeId);
  if (!existingStore) return res.status(404).json({ error: '门店不存在' });

  db.prepare(`
    INSERT INTO store_month_plans (store_id, month, target_frequency, reason, updated_by, updated_at)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(store_id, month) DO UPDATE SET
      target_frequency=excluded.target_frequency,
      reason=excluded.reason,
      updated_by=excluded.updated_by,
      updated_at=CURRENT_TIMESTAMP
  `).run(storeId, month, Math.trunc(target), reason || '', req.user.id);
  res.json({ success: true });
});

app.delete('/api/stores/:id/month-plan', authenticateToken, isAdmin, (req, res) => {
  const storeId = req.params.id;
  const month = String(req.query.month || '');
  if (!month) return res.status(400).json({ error: 'Missing month' });
  db.prepare('DELETE FROM store_month_plans WHERE store_id = ? AND month = ?').run(storeId, month);
  res.json({ success: true });
});

app.post('/api/stores/batch', authenticateToken, isAdmin, (req, res) => {
  const stores = req.body;
  const startMonth = formatLocalMonth();
  const insert = db.prepare(`
    INSERT INTO stores (
      id,
      name,
      brand,
      province,
      city,
      assigned_expert,
      monthly_frequency,
      special_requirements,
      import_status,
      service_start_month,
      service_resume_month,
      deleted_at
    )
    VALUES (
      @id,
      @name,
      @brand,
      @province,
      @city,
      @assignedExpert,
      @monthlyFrequency,
      @specialRequirements,
      @importStatus,
      @serviceStartMonth,
      @serviceResumeMonth,
      @deletedAt
    )
    ON CONFLICT(id) DO UPDATE SET
      name=excluded.name, 
      brand=excluded.brand,
      province=excluded.province,
      city=excluded.city,
      assigned_expert=excluded.assigned_expert, 
      monthly_frequency=excluded.monthly_frequency,
      special_requirements=excluded.special_requirements,
      import_status=excluded.import_status
  `);

  const insertMany = db.transaction((data) => {
    for (const store of data) {
      const payload = {
        id: store.id,
        name: store.name,
        brand: store.brand || '',
        province: store.province || '',
        city: store.city || '',
        assignedExpert: store.assignedExpert || '',
        monthlyFrequency: store.monthlyFrequency || 1,
        specialRequirements: store.specialRequirements || '',
        importStatus: store.importStatus || null,
        serviceStartMonth: store.serviceStartMonth || startMonth,
        serviceResumeMonth: store.serviceResumeMonth || null,
        deletedAt: store.deletedAt || null
      };
      insert.run(payload);
    }
  });
  try { insertMany(stores); res.json({ success: true, count: stores.length }); } catch (err) { res.status(500).json({ error: err.message }); }
});

app.put('/api/stores/:id', authenticateToken, (req, res) => {
  const { id } = req.params;
  const store = req.body;
  const role = req.user.role;

  try {
    const existing = db.prepare('SELECT * FROM stores WHERE id = ?').get(id);
    if (!existing) return res.status(404).json({ error: '门店不存在' });

    let sql = 'UPDATE stores SET ';
    const params = [];

    if (role === 'admin') {
      // 管理员：允许更新所有字段
      sql += `name=?, brand=?, province=?, city=?, assigned_expert=?, monthly_frequency=?, special_requirements=?, import_status=? WHERE id=?`;
      params.push(
        store.name !== undefined ? store.name : existing.name,
        store.brand !== undefined ? store.brand : existing.brand,
        store.province !== undefined ? store.province : existing.province,
        store.city !== undefined ? store.city : existing.city,
        store.assignedExpert !== undefined ? store.assignedExpert : existing.assigned_expert,
        store.monthlyFrequency !== undefined ? store.monthlyFrequency : existing.monthly_frequency,
        store.specialRequirements !== undefined ? store.specialRequirements : existing.special_requirements,
        store.importStatus !== undefined ? store.importStatus : existing.import_status,
        id
      );
    } else {
      // 普通用户：仅允许更新 频次、专家
      // 字段级权限验证：如果尝试修改其他字段，忽略或报错。这里选择忽略非授权字段，仅更新授权字段。
      sql += `assigned_expert=?, monthly_frequency=? WHERE id=?`;
      params.push(
        store.assignedExpert !== undefined ? store.assignedExpert : existing.assigned_expert,
        store.monthlyFrequency !== undefined ? store.monthlyFrequency : existing.monthly_frequency,
        id
      );
    }

    db.prepare(sql).run(...params);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.delete('/api/stores/:id', authenticateToken, isAdmin, (req, res) => {
  try {
    const storeId = req.params.id;
    const existing = db.prepare('SELECT * FROM stores WHERE id = ?').get(storeId);
    if (!existing) return res.status(404).json({ error: '门店不存在' });

    const today = formatLocalDate();
    const plannedCount = db.prepare(`SELECT COUNT(*) as cnt FROM visits WHERE store_id = ? AND status = 'planned' AND date >= ?`).get(storeId, today).cnt;
    if (plannedCount > 0) {
      return res.status(409).json({ error: '存在待执行排班（planned），请先取消或改期后再停用门店' });
    }

    db.prepare(`UPDATE stores SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?`).run(storeId);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err instanceof Error ? err.message : String(err) });
  }
});

app.post('/api/stores/:id/restore', authenticateToken, isAdmin, (req, res) => {
  try {
    const storeId = req.params.id;
    const existing = db.prepare('SELECT * FROM stores WHERE id = ?').get(storeId);
    if (!existing) return res.status(404).json({ error: '门店不存在' });

    db.prepare(`UPDATE stores SET deleted_at = NULL, service_resume_month = ? WHERE id = ?`).run(formatLocalMonth(), storeId);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err instanceof Error ? err.message : String(err) });
  }
});

app.get('/api/visits', authenticateToken, (req, res) => {
  const { month } = req.query;
  let sql = 'SELECT * FROM visits';
  if (month) sql += ` WHERE date LIKE '${month}%'`;
  const visits = db.prepare(sql).all().map(v => ({
    id: v.id,
    storeId: v.store_id,
    date: v.date,
    expertName: v.expert_name,
    status: v.status,
    type: v.type || 'regular',
    title: v.title || '',
    countTowardsTarget: v.count_towards_target === 0 ? false : true,
    createdBy: v.created_by || null,
    createdAt: v.created_at || null
  }));
  res.json(visits);
});

app.post('/api/visits', authenticateToken, (req, res) => {
  const { id, storeId, date, expertName, status, type, title, countTowardsTarget } = req.body || {};
  if (!id || !storeId || !date || !expertName) return res.status(400).json({ error: 'Missing id/storeId/date/expertName' });
  if (req.user.role !== 'admin' && expertName !== req.user.name) {
    return res.status(403).json({ error: 'Permission denied' });
  }
  const store = db.prepare('SELECT id, deleted_at FROM stores WHERE id = ?').get(storeId);
  if (!store) return res.status(404).json({ error: '门店不存在' });
  if (store.deleted_at) return res.status(409).json({ error: '门店已停用，无法创建排班' });

  const visitType = type === 'extra' ? 'extra' : 'regular';
  const resolvedTitle = String(title || '');
  if (visitType === 'extra' && !resolvedTitle.trim()) return res.status(400).json({ error: 'Missing title' });
  const resolvedStatus = status || 'planned';
  const resolvedCountToward = countTowardsTarget !== undefined
    ? (countTowardsTarget ? 1 : 0)
    : (visitType === 'extra' ? 0 : 1);
  try {
    db.prepare(`
      INSERT INTO visits (id, store_id, date, expert_name, status, type, title, count_towards_target, created_by, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    `).run(id, storeId, date, expertName, resolvedStatus, visitType, resolvedTitle, resolvedCountToward, req.user.id);
    res.json({ success: true });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

app.put('/api/visits/:id', authenticateToken, (req, res) => {
  const { id } = req.params;
  const { date, status, title, countTowardsTarget } = req.body || {};
  if (!date && !status && title === undefined && countTowardsTarget === undefined) return res.status(400).json({ error: 'Missing update fields' });
  try {
    const existing = db.prepare('SELECT * FROM visits WHERE id = ?').get(id);
    if (!existing) return res.status(404).json({ error: '排班不存在' });
    if (req.user.role !== 'admin' && existing.expert_name !== req.user.name) {
      return res.status(403).json({ error: 'Permission denied' });
    }
    const newDate = date || existing.date;
    const newStatus = status || existing.status;
    const newTitle = title !== undefined ? String(title || '') : (existing.title || '');
    const newCount = countTowardsTarget !== undefined ? (countTowardsTarget ? 1 : 0) : (existing.count_towards_target ?? 1);
    db.prepare('UPDATE visits SET date = ?, status = ?, title = ?, count_towards_target = ? WHERE id = ?').run(newDate, newStatus, newTitle, newCount, id);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.delete('/api/visits/:id', authenticateToken, (req, res) => {
  try {
    const existing = db.prepare('SELECT * FROM visits WHERE id = ?').get(req.params.id);
    if (!existing) return res.status(404).json({ error: '排班不存在' });
    if (req.user.role !== 'admin' && existing.expert_name !== req.user.name) {
      return res.status(403).json({ error: 'Permission denied' });
    }
    db.prepare('DELETE FROM visits WHERE id = ?').run(req.params.id);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/experts', authenticateToken, (req, res) => {
  // 从 users 表获取所有用户作为专家列表
  const experts = db.prepare('SELECT name FROM users WHERE status = 1').all().map(e => e.name);
  res.json(experts);
});

// 废弃旧的专家管理 API
// app.post('/api/experts', ...);
// app.delete('/api/experts/:name', ...);

// --- 静态资源服务 (部署配置) ---

// 1. 个人空间主页 (Landing Page) -> /workspace
app.use('/workspace', express.static(path.join(__dirname, 'landing_page')));

// 2. 排班系统 (Service Mate) -> /workspace/schedule
// 注意：Service Mate 需使用 build 后的 dist 目录
app.use('/workspace/schedule', express.static(path.join(__dirname, 'service-mate/dist')));

// 3. SPA 回退路由 (确保排班系统刷新后路由正常)
app.get(/\/workspace\/schedule\/.*/, (req, res) => {
  res.sendFile(path.join(__dirname, 'service-mate/dist/index.html'));
});

// 4. 根路径重定向
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'landing_page/home.html'));
});

app.listen(PORT, () => {
  console.log(`ServicePlan Mate API running on http://localhost:${PORT}`);
});
