from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from auto_scheduler.config_store import load_default_config
from auto_scheduler.engine import run_schedule


def _input_rows(count: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "门店ID": f"store-{index}",
                "门店名称": f"测试门店{index}",
                "品牌": "普通品牌",
                "省份": "测试省",
                "城市": "测试市",
                "行政区划": "测试区",
                "经度": 120.0 + index / 10000,
                "纬度": 30.0 + index / 10000,
                "服务人员": "测试专家",
                "本月需要服务次数": 1,
                "上月服务日期": "2026-01-01",
                "指定日期": "",
            }
            for index in range(count)
        ]
    )


def _strict_config() -> dict:
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 2,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 1,
            "MAX_DAILY_ORDERS_PER_PERSON_RELAXED": 1,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 2,
            "REGULAR_FREQ1_WINDOW_DAYS": 1,
        }
    )
    return config


def test_capacity_conflicts_are_reported_instead_of_overbooking():
    result = run_schedule(_input_rows(), _strict_config())

    assert result.summary["预期服务任务"] == 5
    assert result.summary["成功排班数"] == 1
    assert result.summary["硬规则冲突数"] == 4
    assert set(result.anomalies["处理状态"]) == {"待人工排班"}
    daily = result.scheduled.groupby(["服务人员", "服务锚点日期"]).size()
    assert daily.max() == 1


def test_same_input_and_config_are_deterministic():
    first = run_schedule(_input_rows(3), _strict_config())
    second = run_schedule(_input_rows(3), _strict_config())

    assert first.summary == second.summary
    assert_frame_equal(first.scheduled, second.scheduled)
    assert_frame_equal(first.anomalies, second.anomalies)


def test_supported_frequencies_are_accounted_for():
    dataframe = _input_rows(6)
    dataframe["本月需要服务次数"] = [0, 0.3, 1, 2, 3, 4]
    dataframe["上月服务日期"] = ["2026-01-01"] * 6
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 20,
            "MAX_DAILY_ORDERS_PER_PERSON_RELAXED": 20,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 100,
        }
    )

    result = run_schedule(dataframe, config)

    assert result.summary["预期服务任务"] == 11
    assert result.summary["成功排班数"] + result.summary["硬规则冲突数"] == 11
    assert result.summary["未生成任务数"] == 0


def test_fixed_holiday_date_is_scheduled_with_visible_warning():
    dataframe = _input_rows(1)
    dataframe.loc[0, "指定日期"] = "8月5日"
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [(5, 5)],
            "MAX_DAILY_ORDERS_PER_PERSON": 10,
            "MAX_DAILY_ORDERS_PER_PERSON_RELAXED": 10,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 100,
        }
    )

    result = run_schedule(dataframe, config)

    assert result.scheduled.iloc[0]["服务锚点日期"].day == 5
    assert result.summary["规则警告数"] == 1
    assert "假期冲撞" in result.anomalies.iloc[0]["异常原因"]


def test_remote_and_brand_range_rules_are_preserved():
    dataframe = _input_rows(2)
    dataframe.loc[0, "行政区划"] = "张家港市"
    dataframe.loc[1, "品牌"] = "塔斯汀中国汉堡"
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 10,
            "MAX_DAILY_ORDERS_PER_PERSON_RELAXED": 10,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 100,
        }
    )

    result = run_schedule(dataframe, config)
    notes = dict(zip(result.scheduled["门店ID"], result.scheduled["排班逻辑"], strict=True))

    assert "偏远门店" in notes["store-0"]
    assert "3天范围门店" in notes["store-1"]


def test_future_month_in_same_year_is_treated_as_previous_year_for_quarterly_work():
    dataframe = _input_rows(1)
    dataframe["本月需要服务次数"] = dataframe["本月需要服务次数"].astype(float)
    dataframe.loc[0, "本月需要服务次数"] = 0.3
    dataframe.loc[0, "上月服务日期"] = "2026-12-01"
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 10,
            "MAX_DAILY_ORDERS_PER_PERSON_RELAXED": 10,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 100,
        }
    )

    result = run_schedule(dataframe, config)

    assert result.summary["预期服务任务"] == 1
    assert result.summary["成功排班数"] == 1
