from __future__ import annotations

from datetime import date

import pandas as pd

from auto_scheduler.config_store import load_default_config
from auto_scheduler.engine import run_schedule


def _as_date(value) -> date:
    return pd.Timestamp(value).date()


def _tashi_rows(count: int, last_date: str = "2026-09-13") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "门店ID": f"tashi-{index}",
                "门店名称": f"塔斯汀中国汉堡(测试{index}店)",
                "品牌": "塔斯汀中国汉堡",
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
            "MONTH": 10,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 4,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 100,
            "MAX_MONTHLY_WORKDAYS_PER_PERSON": 31,
        }
    )
    config.update(overrides)
    return config


def test_tashi_window_ends_thirty_days_after_last_service():
    result = run_schedule(_tashi_rows(1), _config())

    row = result.scheduled.iloc[0]
    assert _as_date(row["开始日期"]) == date(2026, 10, 11)
    assert _as_date(row["截止日期"]) == date(2026, 10, 13)
    interval = (_as_date(row["服务锚点日期"]) - date(2026, 9, 13)).days
    assert 28 <= interval <= 30
    assert "3天范围门店" in row["排班逻辑"]
    assert result.summary["硬规则冲突数"] == 0


def test_tashi_window_shifts_only_when_whole_window_hits_holiday():
    result = run_schedule(
        _tashi_rows(1, last_date="2026-09-02"),
        _config(HOLIDAY_BLOCKS=[(1, 3)]),
    )

    row = result.scheduled.iloc[0]
    service_day = _as_date(row["服务锚点日期"])
    assert "假期避让" in row["排班逻辑"]
    assert _as_date(row["开始日期"]) <= service_day <= _as_date(row["截止日期"])
    assert service_day > date(2026, 10, 3)
    assert (service_day - date(2026, 9, 2)).days > 30


def test_tashi_window_that_cannot_fit_capacity_goes_to_conflicts():
    result = run_schedule(_tashi_rows(4), _config(MAX_DAILY_ORDERS_PER_PERSON=1))

    assert result.summary["成功排班数"] == 3
    assert result.summary["硬规则冲突数"] == 1
    assert "容量" in result.anomalies.iloc[0]["异常原因"]


def test_month_start_last_service_keeps_window_inside_the_band():
    """上月 2 号上门时，窗口收口到本月 1 号，仍落在 25~30 天硬区间内。"""
    result = run_schedule(
        _tashi_rows(1, last_date="2026-07-02"),
        _config(MONTH=8),
    )

    row = result.scheduled.iloc[0]
    assert _as_date(row["开始日期"]) == date(2026, 8, 1)
    assert _as_date(row["截止日期"]) == date(2026, 8, 1)
    assert (_as_date(row["服务锚点日期"]) - date(2026, 7, 2)).days == 30


def test_last_service_too_early_goes_to_conflicts():
    """上月 1 号上门：本月不存在 25~30 天内的日期，转异常待处理。"""
    result = run_schedule(
        _tashi_rows(1, last_date="2026-07-01"),
        _config(MONTH=8),
    )

    assert result.summary["成功排班数"] == 0
    assert result.summary["硬规则冲突数"] == 1
    assert "没有距上月服务日" in result.anomalies.iloc[0]["异常原因"]


def test_other_range_brands_keep_the_same_day_of_month_window():
    dataframe = _tashi_rows(1)
    dataframe.loc[0, "品牌"] = "半天妖烤鱼"
    dataframe.loc[0, "门店名称"] = "半天妖烤鱼(测试店)"

    result = run_schedule(dataframe, _config())

    row = result.scheduled.iloc[0]
    assert _as_date(row["开始日期"]) == date(2026, 10, 12)
    assert _as_date(row["截止日期"]) == date(2026, 10, 14)
