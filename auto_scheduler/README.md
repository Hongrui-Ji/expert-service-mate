# 智能排班生成器

公开的 Streamlit Excel 工具：上传前置表、使用共享规则排班、查看异常并下载新的 Excel。

## 规则文档

完整排班规则（硬约束、软偏好、实测数据、已知边界）见 [`排班算法规则.md`](./排班算法规则.md)。

核心约束速览：

- 每人每天最多 **4 个工单额度**；同一主门店的宿舍合并算 1 个额度
- 每人每周最多 **25 单**；每人每月最多 **25 个工作日**
- 同店相邻两次服务的最小间隔：常规 2/3/≥4 次 → 10/7/5 天，偏远 2/≥3 次 → 10/6 天
- 所有档位的服务窗口固定，不整体平移；窗口内排不下转「异常待处理」

## 本地启动

```bash
python3 -m venv auto_scheduler/.venv
auto_scheduler/.venv/bin/pip install -r auto_scheduler/requirements.txt
SCHEDULER_CONFIG_PATH=/tmp/auto-scheduler-config.json \
  auto_scheduler/.venv/bin/python -m streamlit run auto_scheduler/app.py \
  --server.address 127.0.0.1 \
  --server.port 8503 \
  --server.baseUrlPath auto-schedule \
  --server.maxUploadSize 10 \
  --server.headless true
```

访问 `http://127.0.0.1:8503/auto-schedule/`。

## 数据边界

- 只读取当前上传的 `.xlsx`，最大 10 MB、20,000 行。
- 输入与生成结果都只保存在当前进程会话内存中。
- 不连接项目现有 SQLite，不读取或写入门店、专家或排班数据。
- 共享业务规则保存在 `SCHEDULER_CONFIG_PATH` 指向的 JSON 文件中；未设置时使用 `~/.zeosite/auto-scheduler/config.json`。

## 测试

```bash
auto_scheduler/.venv/bin/pip install -r auto_scheduler/requirements-dev.txt
auto_scheduler/.venv/bin/python -m pytest -q auto_scheduler/tests
```
