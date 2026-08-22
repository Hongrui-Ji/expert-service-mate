from __future__ import annotations

import re
from calendar import monthrange
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from auto_scheduler.config_store import (
    ConfigError,
    load_config,
    load_default_config,
    restore_default_config,
    save_config,
    validate_config,
)
from auto_scheduler.engine import ScheduleRunResult, run_schedule
from auto_scheduler.excel_io import (
    MAX_UPLOAD_BYTES,
    build_output_workbook,
    read_input_workbook,
)

st.set_page_config(page_title="智能排班生成器", page_icon="📅", layout="wide")

st.markdown(
    """
    <style>
      .stApp { background: #f6f8fc; }
      .block-container { max-width: 1280px; padding-top: 2rem; padding-bottom: 4rem; }
      .hero { background: linear-gradient(135deg,#1d4ed8,#4f46e5); color: white;
              border-radius: 20px; padding: 26px 30px; margin-bottom: 20px;
              box-shadow: 0 14px 32px rgba(29,78,216,.18); }
      .hero h1 { margin: 0 0 8px; font-size: 30px; }
      .hero p { margin: 0; opacity: .9; }
      div[data-testid="stMetric"] { background: white; border: 1px solid #e5e7eb;
              padding: 14px 16px; border-radius: 14px; }
      div[data-testid="stFileUploader"] { background: white; border-radius: 14px; padding: 8px 12px; }
    </style>
    <div class="hero">
      <h1>智能排班生成器</h1>
      <p>上传 Excel，按当前规则自动排班，检查异常后下载新的排班结果。</p>
    </div>
    """,
    unsafe_allow_html=True,
)


NUMERIC_FIELDS = (
    ("SOFT_ANCHOR_TOLERANCE", "锚点容忍天数", 0, 31),
    ("MAX_DAILY_ORDERS_PER_PERSON", "每日严格上限", 1, 20),
    ("MAX_DAILY_ORDERS_PER_PERSON_RELAXED", "每日放宽上限", 1, 20),
    ("RELAXED_CAP_BEFORE_DAY", "放宽截止日", 1, 31),
    ("MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON", "每周容量上限", 1, 100),
    ("NEARBY_ALIGN_RADIUS_METERS", "近邻半径（米）", 0, 100000),
    ("REMOTE_DAILY_PAIR_TARGET", "偏远门店同日聚合目标", 1, 20),
    ("REMOTE_MIN_GAP_DAYS_FREQ2", "偏远频次2最小间隔", 0, 31),
    ("REMOTE_MIN_GAP_DAYS_FREQ3PLUS", "偏远频次3+最小间隔", 0, 31),
    ("REGULAR_MIN_GAP_DAYS_FREQ2", "常规频次2最小间隔", 0, 31),
    ("REGULAR_MIN_GAP_DAYS_FREQ3", "常规频次3最小间隔", 0, 31),
    ("REGULAR_MIN_GAP_DAYS_FREQ4PLUS", "常规频次4+最小间隔", 0, 31),
    ("REMOTE_MAX_SHIFT_DAYS", "偏远窗口最大顺移天数", 0, 31),
    ("BRAND_RANGE_MAX_HOLIDAY_DAYS", "三日范围最大假期天数", 0, 3),
    ("REGULAR_FREQ1_WINDOW_DAYS", "单次服务窗口天数", 1, 31),
    ("QUARTERLY_INTERVAL_MONTHS", "季度门店最小间隔（月）", 1, 24),
    ("SMOOTHING_ANCHOR_WEIGHT", "平滑：锚点偏离权重", 0, 1000),
    ("SMOOTHING_DAY_LOAD_WEIGHT", "平滑：当日负载权重", 0, 1000),
    ("SMOOTHING_NEIGHBOR_LOAD_WEIGHT", "平滑：相邻日负载权重", 0, 1000),
    ("SMOOTHING_NEARBY_ALIGN_BONUS", "平滑：近邻同日奖励", 0, 1000),
)
WIDGET_KEYS = ["remote_editor", "date_brand_editor", "range_brand_editor"] + [
    f"config_{field[0]}" for field in NUMERIC_FIELDS
]


def _load_rules() -> dict:
    try:
        return load_config()
    except ConfigError as exc:
        st.warning(f"共享配置无法读取，当前临时使用默认值：{exc}")
        return load_default_config()


def _clear_config_widgets():
    for key in WIDGET_KEYS:
        st.session_state.pop(key, None)


def _list_editor(title: str, values: list[str], key: str, help_text: str) -> list[str]:
    st.markdown(f"**{title}**")
    st.caption(help_text)
    edited = st.data_editor(
        pd.DataFrame({"名称": values}),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key=key,
        column_config={"名称": st.column_config.TextColumn("名称", required=False)},
    )
    return [str(value).strip() for value in edited["名称"].tolist() if str(value).strip()]


def _render_config_editor(base_config: dict) -> dict:
    top_left, top_right = st.columns([1, 1])
    with top_left:
        if st.button("恢复默认配置", type="secondary", width="stretch"):
            try:
                restored = restore_default_config()
            except (ConfigError, OSError) as exc:
                st.error(f"恢复失败：{exc}")
            else:
                st.session_state.shared_rules = restored
                _clear_config_widgets()
                st.success("已恢复默认配置")
                st.rerun()
    with top_right:
        st.info("此处修改的是所有使用者共享的一套规则。")

    list_col1, list_col2, list_col3 = st.columns(3)
    with list_col1:
        remote_cities = _list_editor(
            "偏远城市/区域",
            base_config["REMOTE_CITIES"],
            "remote_editor",
            "点击末行可新增，选中行后可删除。",
        )
    with list_col2:
        date_brands = _list_editor(
            "单日锁定品牌",
            base_config["SPECIFIC_DATE_BRANDS"],
            "date_brand_editor",
            "这些品牌使用单日锚点规则。",
        )
    with list_col3:
        range_brands = _list_editor(
            "三日范围品牌",
            base_config["SPECIFIC_RANGE_BRANDS"],
            "range_brand_editor",
            "这些品牌使用三日服务窗口规则。",
        )

    st.divider()
    st.markdown("#### 容量、间隔与平滑参数")
    numeric_values: dict[str, int] = {}
    columns = st.columns(4)
    for index, (key, label, minimum, maximum) in enumerate(NUMERIC_FIELDS):
        with columns[index % 4]:
            numeric_values[key] = int(
                st.number_input(
                    label,
                    min_value=minimum,
                    max_value=maximum,
                    value=int(base_config[key]),
                    step=1,
                    key=f"config_{key}",
                )
            )

    current = dict(base_config)
    current.update(numeric_values)
    current["REMOTE_CITIES"] = remote_cities
    current["SPECIFIC_DATE_BRANDS"] = date_brands
    current["SPECIFIC_RANGE_BRANDS"] = range_brands

    if st.button("保存共享配置", type="primary", width="stretch"):
        try:
            current = save_config(current)
        except (ConfigError, OSError) as exc:
            st.error(f"配置保存失败：{exc}")
        else:
            st.session_state.shared_rules = current
            st.success("共享配置已保存，刷新页面或重启服务后仍会生效。")
    return current


def _holiday_blocks(table: pd.DataFrame, days_in_month: int) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    for _, row in table.iterrows():
        if pd.isna(row.get("开始日")) or pd.isna(row.get("结束日")):
            continue
        start = int(row["开始日"])
        end = int(row["结束日"])
        if start < 1 or end < start or end > days_in_month:
            raise ValueError(f"节假日区间 {start}-{end} 不在当月有效日期内")
        blocks.append((start, end))
    return blocks


def _safe_download_name(upload_name: str, year: int, month: int) -> str:
    stem = re.sub(r"[^\w\-\u4e00-\u9fff]+", "_", upload_name.rsplit(".", 1)[0]).strip("_")
    stem = stem[:60] or "上传文件"
    return f"排班结果_{stem}_{year}年{month}月.xlsx"


def _show_result(result: ScheduleRunResult, output_bytes: bytes, download_name: str):
    summary = result.summary
    metrics = st.columns(5)
    metrics[0].metric("输入门店", summary["输入门店数"])
    metrics[1].metric("预期任务", summary["预期服务任务"])
    metrics[2].metric("成功排班", summary["成功排班数"])
    metrics[3].metric("硬规则冲突", summary["硬规则冲突数"])
    metrics[4].metric("规则警告", summary["规则警告数"])

    if not result.anomalies.empty:
        st.warning(f"发现 {len(result.anomalies)} 条异常或提醒，请下载结果后查看“异常待处理”Sheet。")
    else:
        st.success("排班完成，本次未发现异常。")

    preview_tab, anomaly_tab = st.tabs(["排班预览", "异常提示"])
    with preview_tab:
        if result.scheduled.empty:
            st.info("没有生成排班记录。")
        else:
            st.dataframe(result.scheduled.head(500), width="stretch", hide_index=True)
            if len(result.scheduled) > 500:
                st.caption("页面仅预览前 500 条，下载文件包含完整结果。")
    with anomaly_tab:
        if result.anomalies.empty:
            st.info("没有异常记录。")
        else:
            st.dataframe(result.anomalies, width="stretch", hide_index=True)

    st.download_button(
        "下载排班结果 Excel",
        data=output_bytes,
        file_name=download_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        width="stretch",
    )


if "shared_rules" not in st.session_state:
    st.session_state.shared_rules = _load_rules()

generate_tab, config_tab = st.tabs(["生成排班", "规则配置"])

# Streamlit renders all tab bodies on every run. Render configuration first so
# the Generate button always uses the currently visible widget values.
with config_tab:
    current_rules = _render_config_editor(st.session_state.shared_rules)

with generate_tab:
    st.markdown("### 1. 上传前置表")
    uploaded = st.file_uploader(
        "选择 Excel 文件",
        type=["xlsx"],
        accept_multiple_files=False,
        help="仅支持 .xlsx，文件最大 10 MB。上传内容只在当前会话内存中处理。",
    )

    st.markdown("### 2. 设置本次运行参数")
    now = datetime.now(tz=ZoneInfo("Asia/Shanghai"))
    run_col1, run_col2, run_col3 = st.columns(3)
    with run_col1:
        target_year = int(st.number_input("年份", min_value=2020, max_value=2100, value=now.year, step=1))
    with run_col2:
        target_month = int(st.selectbox("月份", options=list(range(1, 13)), index=now.month - 1))
    with run_col3:
        split_by_province = st.checkbox("按省份拆分 Sheet", value=True)

    days_in_month = monthrange(target_year, target_month)[1]
    st.markdown("**节假日区间（可选）**")
    holiday_table = st.data_editor(
        pd.DataFrame(columns=["开始日", "结束日"]),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="holiday_editor",
        column_config={
            "开始日": st.column_config.NumberColumn("开始日", min_value=1, max_value=days_in_month, step=1),
            "结束日": st.column_config.NumberColumn("结束日", min_value=1, max_value=days_in_month, step=1),
        },
    )

    can_run = uploaded is not None
    if st.button("开始生成排班", type="primary", disabled=not can_run, width="stretch"):
        try:
            if uploaded is None:
                raise ValueError("请先上传 Excel 文件")
            content = uploaded.getvalue()
            if len(content) > MAX_UPLOAD_BYTES:
                raise ValueError("Excel 文件不能超过 10 MB")
            validated_rules = validate_config(current_rules)
            validated_rules.update(
                {
                    "YEAR": target_year,
                    "MONTH": target_month,
                    "HOLIDAY_BLOCKS": _holiday_blocks(holiday_table, days_in_month),
                    "OUTPUT_SPLIT_BY_PROVINCE": split_by_province,
                }
            )
            with st.spinner("正在读取 Excel 并生成排班……"):
                input_frame = read_input_workbook(content)
                schedule_result = run_schedule(input_frame, validated_rules)
                output_bytes = build_output_workbook(
                    schedule_result,
                    split_by_province=split_by_province,
                )
            st.session_state.schedule_output = {
                "result": schedule_result,
                "bytes": output_bytes,
                "name": _safe_download_name(uploaded.name, target_year, target_month),
            }
        except (ValueError, ConfigError, OSError) as exc:
            st.session_state.pop("schedule_output", None)
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001 - surface unexpected workbook/algorithm errors in the public UI
            st.session_state.pop("schedule_output", None)
            st.error(f"排班运行失败：{exc}")

    if "schedule_output" in st.session_state:
        st.divider()
        st.markdown("### 3. 查看并下载结果")
        stored = st.session_state.schedule_output
        _show_result(stored["result"], stored["bytes"], stored["name"])

st.caption("本工具不会读取或写入专家工作园地现有数据库，也不会保存上传文件和输出文件。")
