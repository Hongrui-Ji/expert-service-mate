from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from auto_scheduler.config_store import load_default_config
from auto_scheduler.engine import ProductionScheduler, run_schedule
from auto_scheduler.legacy_core import DEFAULT_CONFIG


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
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 100,
        }
    )

    result = run_schedule(dataframe, config)

    assert result.scheduled.iloc[0]["服务锚点日期"].day == 5
    assert result.summary["规则警告数"] == 1
    assert "假期冲撞" in result.anomalies.iloc[0]["异常原因"]


def test_single_weekday_requirements_search_the_whole_month():
    dataframe = _input_rows(3)
    dataframe["指定日期"] = ["周一", "每周五", "星期三"]
    dataframe["本月需要服务次数"] = 2
    config = dict(_strict_config(), MONTH=12)

    result = run_schedule(dataframe, config)
    scheduled_days = {
        store_id: [day.day for day in days]
        for store_id, days in result.scheduled.groupby("门店ID")["服务锚点日期"]
    }

    # 同一专家每周最多两单，周三门店使用仍有容量的第二周和第四周。
    assert scheduled_days == {"store-0": [7, 21], "store-1": [4, 18], "store-2": [9, 23]}
    assert result.anomalies.empty
    assert (result.scheduled["开始日期"] == result.scheduled["截止日期"]).all()


def test_single_weekday_moves_to_other_weeks_when_dates_are_unavailable():
    dataframe = _input_rows(2)
    dataframe["指定日期"] = ["每周一晚上", "7号"]
    dataframe["本月需要服务次数"] = [2, 1]
    config = dict(_strict_config(), MONTH=12, HOLIDAY_BLOCKS=[(21, 21)])

    result = run_schedule(dataframe, config)
    flexible = result.scheduled[result.scheduled["门店ID"] == "store-0"]

    assert result.anomalies.empty
    assert [day.day for day in flexible["服务锚点日期"]] == [14, 28]
    assert flexible["排班逻辑"].str.contains("晚上").all()
    assert result.scheduled.loc[result.scheduled["门店ID"] == "store-1", "服务锚点日期"].iloc[0].day == 7


def test_single_weekday_reports_unfilled_visits_per_store():
    dataframe = _input_rows(1)
    dataframe["指定日期"] = "周一"
    dataframe["本月需要服务次数"] = 2
    config = dict(_strict_config(), MONTH=12, HOLIDAY_BLOCKS=[(21, 21), (28, 28)])

    result = run_schedule(dataframe, config)

    assert result.summary["成功排班数"] == result.summary["硬规则冲突数"] == 1
    assert result.summary["未生成任务数"] == 0
    assert result.anomalies.iloc[0]["门店ID"] == "store-0"
    assert "指定星期" in result.anomalies.iloc[0]["异常原因"]


def test_single_weekday_respects_remaining_monthly_workdays_for_the_combination():
    dataframe = _input_rows(1)
    dataframe["指定日期"] = "周一"
    dataframe["本月需要服务次数"] = 2
    config = dict(_strict_config(), MONTH=12, MAX_MONTHLY_WORKDAYS_PER_PERSON=1)

    result = run_schedule(dataframe, config)

    assert result.summary["成功排班数"] == result.summary["硬规则冲突数"] == 1
    assert result.scheduled.iloc[0]["服务锚点日期"].day == 7
    assert "指定星期" in result.anomalies.iloc[0]["异常原因"]


def test_explicit_week_numbers_remain_fixed_dates():
    dataframe = _input_rows(1)
    dataframe["指定日期"] = "每月第二周第四周周一"
    dataframe["本月需要服务次数"] = 2

    result = run_schedule(dataframe, dict(_strict_config(), MONTH=12))

    assert result.anomalies.empty
    assert [day.day for day in result.scheduled["服务锚点日期"]] == [14, 28]


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
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 100,
        }
    )

    result = run_schedule(dataframe, config)

    assert result.summary["预期服务任务"] == 1
    assert result.summary["成功排班数"] == 1


def test_work_is_spread_across_days():
    """互不相邻的门店要把工单摊开，不先把单日额度占满、月底留空。"""
    dataframe = _input_rows(8)
    dataframe["上月服务日期"] = "2026-07-15"
    # 让门店彼此相距约 1.5 公里，排除近邻同日的干扰，单独检验负载均衡
    for index in range(8):
        dataframe.loc[index, "纬度"] = 30.0 + index * 0.015
        dataframe.loc[index, "经度"] = 120.0 + index * 0.015
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 4,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 25,
            "MAX_MONTHLY_WORKDAYS_PER_PERSON": 25,
        }
    )

    result = run_schedule(dataframe, config)

    assert result.summary["成功排班数"] == 8
    per_day = result.scheduled.groupby("服务锚点日期").size()
    assert per_day.max() <= 4
    assert len(per_day) >= 6, "8 单应摊开到至少 6 天，而不是先占满单日额度"


def _apart_rows(count: int) -> pd.DataFrame:
    """生成相互远离、排除近邻同日干扰的门店样本。"""
    dataframe = _input_rows(count)
    dataframe["上月服务日期"] = "2026-07-15"
    for index in range(count):
        dataframe.loc[index, "纬度"] = 20.0 + index * 0.02
        dataframe.loc[index, "经度"] = 100.0 + index * 0.02
    return dataframe


def test_monthly_workday_limit_caps_workdays():
    """每月工作日上限是硬约束：超出后不再新开工作日，改为转异常。"""
    dataframe = _apart_rows(20)
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 4,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 100,
            "MAX_MONTHLY_WORKDAYS_PER_PERSON": 3,
        }
    )

    result = run_schedule(dataframe, config)

    workdays = result.scheduled["服务锚点日期"].nunique()
    assert workdays <= 3
    assert result.summary["硬规则冲突数"] >= 1


def test_dorm_stores_share_one_daily_slot():
    """同一主门店下的多个宿舍，当天合计只占 1 个日额度，因此可超过每日 4 单上限。"""
    dataframe = _input_rows(6)
    dataframe["门店名称"] = [f"很久以前（测试商场店）-宿舍{i + 1}" for i in range(6)]
    dataframe["品牌"] = "很久以前羊肉串"
    dataframe["上月服务日期"] = "2026-07-15"
    for index in range(6):
        dataframe.loc[index, "纬度"] = 30.0
        dataframe.loc[index, "经度"] = 120.0
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 2,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 25,
            "MAX_MONTHLY_WORKDAYS_PER_PERSON": 25,
        }
    )

    result = run_schedule(dataframe, config)

    per_day = result.scheduled.groupby("服务锚点日期").size()
    assert result.summary["成功排班数"] == 6
    assert len(per_day) == 1, "同主门店的宿舍应并到同一天"
    assert per_day.max() == 6, "宿舍组只占 1 个日额度，可突破每日 2 单上限"


def test_dorm_stores_merge_even_when_beyond_nearby_radius():
    """宿舍之间常相距 200~600 米，超出近邻半径，仍应并到同一天（靠同组信号）。"""
    dataframe = _input_rows(3)
    dataframe["门店名称"] = [f"很久以前（测试商场店）-宿舍{i + 1}" for i in range(3)]
    dataframe["品牌"] = "很久以前羊肉串"
    dataframe["上月服务日期"] = "2026-07-15"
    # 三个宿舍相隔约 300 米，均超过 150 米近邻半径
    for index in range(3):
        dataframe.loc[index, "纬度"] = 30.0
        dataframe.loc[index, "经度"] = 120.0 + index * 0.003
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 1,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 25,
            "MAX_MONTHLY_WORKDAYS_PER_PERSON": 25,
        }
    )

    result = run_schedule(dataframe, config)

    assert result.summary["成功排班数"] == 3
    assert result.scheduled["服务锚点日期"].nunique() == 1, "同主门店的宿舍应并到同一天"


def test_frequency_three_windows_are_locked_to_three_periods():
    """频次 3 的窗口固定为三旬区间，不因容量压力整体平移。"""
    dataframe = _input_rows(1)
    dataframe["本月需要服务次数"] = 3
    config = load_default_config()
    config.update({"YEAR": 2026, "MONTH": 8, "HOLIDAY_BLOCKS": []})

    result = run_schedule(dataframe, config)

    windows = sorted(
        (start.day, end.day)
        for start, end in zip(result.scheduled["开始日期"], result.scheduled["截止日期"])
    )
    assert windows == [(1, 10), (11, 20), (21, 31)]


def test_frequency_three_windows_stay_fixed_under_capacity_pressure():
    """容量紧张时，频次 3 的窗口仍保持三旬区间，排不下的部分转异常。"""
    dataframe = _input_rows(4)
    dataframe["本月需要服务次数"] = [3, 1, 1, 1]
    dataframe["上月服务日期"] = "2026-07-15"
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 1,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 2,
        }
    )

    result = run_schedule(dataframe, config)

    freq3 = result.scheduled[result.scheduled["门店ID"] == "store-0"]
    windows = sorted((start.day, end.day) for start, end in zip(freq3["开始日期"], freq3["截止日期"]))
    assert all(window in [(1, 10), (11, 20), (21, 31)] for window in windows)
    assert result.summary["成功排班数"] + result.summary["硬规则冲突数"] >= 4


def _balance_scheduler() -> ProductionScheduler:
    config = dict(DEFAULT_CONFIG)
    config.update(load_default_config())
    config.update({"YEAR": 2026, "MONTH": 8, "HOLIDAY_BLOCKS": []})
    return ProductionScheduler(config)


def test_same_mall_alignment_outranks_daily_load():
    """近邻第 1 位：同商场同日优先于当天负载（单日上限由容量硬校验单独把关）。"""
    scheduler = _balance_scheduler()
    item = {"服务人员": "专家甲", "门店ID": "本店", "纬度": 30.0, "经度": 120.0}
    # 同商场门店已排在 11 号（距离 0 米，属于近邻）
    scheduler.assignment_points_by_person["专家甲"].append(
        {"store_id": "同商场店", "service_person": "专家甲", "lat": 30.0, "lng": 120.0, "service_day": 11}
    )
    # 11 号当天已排 3 单（未满），20 号当天为空
    scheduler.person_day_order_stats[11]["专家甲"] = 3

    assert scheduler._balance_key(11, item, 11) < scheduler._balance_key(20, item, 11)


def test_same_mall_alignment_never_exceeds_daily_cap():
    """即使全部是同商场近邻门店，单日工单数也不会突破日上限。"""
    dataframe = _input_rows(6)
    dataframe["上月服务日期"] = "2026-07-15"
    for index in range(6):  # 6 家门店坐标完全一致 = 互为同商场近邻
        dataframe.loc[index, "纬度"] = 30.0
        dataframe.loc[index, "经度"] = 120.0
    config = load_default_config()
    config.update(
        {
            "YEAR": 2026,
            "MONTH": 8,
            "HOLIDAY_BLOCKS": [],
            "MAX_DAILY_ORDERS_PER_PERSON": 2,
            "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 25,
        }
    )

    result = run_schedule(dataframe, config)

    per_day = result.scheduled.groupby("服务锚点日期").size()
    assert result.summary["成功排班数"] == 6
    assert per_day.max() <= 2
    assert result.summary["硬规则冲突数"] == 0
