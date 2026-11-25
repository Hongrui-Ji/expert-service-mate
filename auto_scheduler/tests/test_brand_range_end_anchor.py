from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

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


def _assert_legal_window(row, last_date: str, month: int):
    previous = _as_date(last_date)
    start = _as_date(row["开始日期"])
    end = _as_date(row["截止日期"])
    service = _as_date(row["服务锚点日期"])
    assert start.month == end.month == month
    assert (end - start).days == 2
    assert 25 <= (start - previous).days <= (end - previous).days <= 35
    assert start <= service <= end


@pytest.mark.parametrize(
    ("last_date", "year", "month"),
    [
        ("2026-09-13", 2026, 10),
        ("2026-07-01", 2026, 8),
        ("2026-01-31", 2026, 2),
        ("2026-12-01", 2027, 1),
    ],
)
def test_tashi_full_window_stays_inside_the_interval_and_target_month(last_date, year, month):
    result = run_schedule(_tashi_rows(1, last_date), _config(YEAR=year, MONTH=month))

    row = result.scheduled.iloc[0]
    _assert_legal_window(row, last_date, month)
    assert "3天范围门店" in row["排班逻辑"]
    assert result.summary["硬规则冲突数"] == 0


def test_tashi_moves_around_holidays_within_interval():
    last_date = "2026-09-13"
    result = run_schedule(_tashi_rows(1, last_date), _config(HOLIDAY_BLOCKS=[(8, 15)]))

    row = result.scheduled.iloc[0]
    _assert_legal_window(row, last_date, 10)
    assert _as_date(row["服务锚点日期"]).day >= 16


def test_tashi_full_interval_blocked_by_holidays_goes_to_conflicts():
    result = run_schedule(_tashi_rows(1), _config(HOLIDAY_BLOCKS=[(8, 18)]))

    assert result.scheduled.empty
    assert result.summary["硬规则冲突数"] == 1
    assert "连续三日窗口" in result.anomalies.iloc[0]["异常原因"]


def test_tashi_uses_full_interval_without_exceeding_daily_capacity():
    last_date = "2026-09-13"
    result = run_schedule(_tashi_rows(12, last_date), _config(MAX_DAILY_ORDERS_PER_PERSON=1))

    assert result.summary["成功排班数"] == 11
    assert result.summary["硬规则冲突数"] == 1
    assert result.scheduled["服务锚点日期"].is_unique
    for _, row in result.scheduled.iterrows():
        _assert_legal_window(row, last_date, 10)
    assert "容量" in result.anomalies.iloc[0]["异常原因"]


@pytest.mark.parametrize(
    ("requirement", "expected_day"),
    [
        ("16到19号", 16),
        ("18号", 18),
        ("周四", 8),
        ("周四或周五", 15),
    ],
)
def test_tashi_special_requirements_keep_a_legal_three_day_window(requirement, expected_day):
    last_date = "2026-09-13"
    dataframe = _tashi_rows(1, last_date)
    dataframe.loc[0, "指定日期"] = requirement

    row = run_schedule(dataframe, _config()).scheduled.iloc[0]
    _assert_legal_window(row, last_date, 10)
    assert _as_date(row["服务锚点日期"]).day == expected_day
    if requirement == "16到19号":
        assert _as_date(row["开始日期"]).day == 16
        assert _as_date(row["截止日期"]).day == 18


@pytest.mark.parametrize("requirement", ["19号", "17到20号"])
def test_tashi_conflicting_special_requirement_goes_to_conflicts(requirement):
    dataframe = _tashi_rows(1)
    dataframe.loc[0, "指定日期"] = requirement

    result = run_schedule(dataframe, _config())
    assert result.scheduled.empty
    assert result.summary["硬规则冲突数"] == 1
    assert "连续三日窗口" in result.anomalies.iloc[0]["异常原因"]


def test_tashi_multiple_visits_never_export_an_out_of_band_window():
    last_date = "2026-09-13"
    dataframe = _tashi_rows(1, last_date)
    dataframe.loc[0, "本月需要服务次数"] = 2

    result = run_schedule(dataframe, _config())
    assert result.summary["成功排班数"] == result.summary["硬规则冲突数"] == 1
    _assert_legal_window(result.scheduled.iloc[0], last_date, 10)


def test_tashi_without_previous_month_history_keeps_the_regular_brand_rule():
    result = run_schedule(_tashi_rows(1, ""), _config())

    assert result.summary["成功排班数"] == 1
    row = result.scheduled.iloc[0]
    assert _as_date(row["开始日期"]) == date(2026, 10, 1)
    assert _as_date(row["截止日期"]) == date(2026, 10, 3)


def test_other_range_brands_keep_the_same_day_of_month_window():
    dataframe = _tashi_rows(1)
    dataframe.loc[0, "品牌"] = "半天妖烤鱼"
    dataframe.loc[0, "门店名称"] = "半天妖烤鱼(测试店)"

    result = run_schedule(dataframe, _config())

    row = result.scheduled.iloc[0]
    assert _as_date(row["开始日期"]) == date(2026, 10, 12)
    assert _as_date(row["截止日期"]) == date(2026, 10, 14)
