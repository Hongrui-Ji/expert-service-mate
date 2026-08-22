# 智能排班生成器

公开的 Streamlit Excel 工具：上传前置表、使用共享规则排班、查看异常并下载新的 Excel。

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
