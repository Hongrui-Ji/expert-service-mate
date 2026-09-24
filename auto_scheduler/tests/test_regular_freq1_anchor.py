from __future__ import annotations

from datetime import date

import pandas as pd

from auto_scheduler.config_store import load_default_config
from auto_scheduler.engine import run_schedule


def _as_date(value) -> date:
    return pd.Timestamp(value).date()


def _rows(count: int, last_date: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "门店ID": f"store-{index}",
                "门店名称": f"常规门店{index}",
                "品牌": "普通品牌",
                "省份": "测试省",
                "城市": "测试市",
                "行政区划": "测试区",
                "经度": 120.0 + index / 100000,
                "纬度": 30.0 + index / 100000,
                "服务人员": "测试专家",
                "本月需要服务次数": 1,
                "上月服务日期": last_date,
                "指定日期": "",
            }
            for index in range(count)
        ]
    )


def _config(**overrides):
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 4,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 100,
            "MAX_MONTHLY_WORKDAYS_PER_PERSON": 31,
        }
    )
    config.update(overrides)
    return config


def test_freq1_anchor_is_thirty_days_after_last_service():
    result = run_schedule(_rows(1, "2026-07-13"), _config())

    row = result.scheduled.iloc[0]
    assert _as_date(row["开始日期"]) == date(2026, 8, 5)
    assert _as_date(row["截止日期"]) == date(2026, 8, 19)
    interval = (_as_date(row["服务锚点日期"]) - date(2026, 7, 13)).days
    assert 23 <= interval <= 37


def test_freq1_window_never_shifts_outside_anchor_plus_minus_seven():
    """容量再紧张，服务日也只能落在固定窗口内。"""
    result = run_schedule(_rows(16, "2026-07-13"), _config(MAX_DAILY_ORDERS_PER_PERSON=1))

    scheduled = result.scheduled
    for _, row in scheduled.iterrows():
        interval = (_as_date(row["服务锚点日期"]) - date(2026, 7, 13)).days
        assert 23 <= interval <= 37
    assert result.summary["成功排班数"] == 15
    assert result.summary["硬规则冲突数"] == 1


def test_freq1_anchor_zero_keeps_legacy_same_day_of_month_window():
    result = run_schedule(_rows(1, "2026-07-13"), _config(REGULAR_FREQ1_ANCHOR_DAYS=0))

    row = result.scheduled.iloc[0]
    assert _as_date(row["开始日期"]) == date(2026, 8, 6)
    assert _as_date(row["截止日期"]) == date(2026, 8, 20)


def test_freq1_month_end_last_service_keeps_window_inside_month():
    result = run_schedule(_rows(1, "2026-07-31"), _config())

    row = result.scheduled.iloc[0]
    assert _as_date(row["开始日期"]) == date(2026, 8, 23)
    assert _as_date(row["截止日期"]) == date(2026, 8, 31)
