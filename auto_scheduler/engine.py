from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from .legacy_core import DEFAULT_CONFIG, AutoSchedulerV2


@dataclass(frozen=True)
class ScheduleRunResult:
    scheduled: pd.DataFrame
    anomalies: pd.DataFrame
    summary: dict[str, Any]


class ProductionScheduler(AutoSchedulerV2):
    """Production-safe adapter around the original scheduling algorithm.

    The legacy implementation treated normal and quarterly work as fractional
    weekly load and could put many service anchors on the same day. This adapter
    applies the configured daily and weekly limits to every concrete anchor and
    records work that cannot be placed instead of silently overbooking it.
    """

    def __init__(self, config: dict[str, Any], *, shared_capacity: dict[str, Any] | None = None):
        super().__init__(config)
        self.conflicts: list[dict[str, Any]] = []
        # 记录「每个自然日、每个人」已经占过日额度的宿舍组：
        # 同一宿舍组在同一自然日只占 1 个额度（一次出勤跑完多个宿舍）。
        self.person_day_slot_groups: dict[int, defaultdict[str, set[str]]] = {
            day: defaultdict(set) for day in range(1, self.days_in_month + 1)
        }
        if shared_capacity is not None:
            self.person_day_order_stats = shared_capacity["days"]
            self.person_week_order_stats = shared_capacity["weeks"]

    def _monthly_workday_limit(self) -> int:
        return int(self.cfg.get("MAX_MONTHLY_WORKDAYS_PER_PERSON", 25))

    def _person_workday_count(self, person: str) -> int:
        return sum(
            1
            for day in range(1, self.days_in_month + 1)
            if self.person_day_order_stats[day].get(person, 0) > 0
        )

    def _day_slot_cost(self, day: int, person: str, item: dict[str, Any]) -> int:
        """本条工单在该自然日占用的日工单额度（同一宿舍组重复出勤时为 0）。"""
        group = self._dorm_group_of(item)
        if group is None:
            return 1
        if group in self.person_day_slot_groups[day].get(person, set()):
            return 0
        return 1

    def _check_person_order_constraint(self, day, item, allow_relaxed=False):
        """日容量 + 周容量 + 每月工作日上限三重校验。

        `allow_relaxed` 仅为兼容旧调用签名保留。
        """
        person = self._get_service_person(item)
        if not person:
            return True

        daily_limit = int(self.cfg.get("MAX_DAILY_ORDERS_PER_PERSON", 4))
        current_day = self.person_day_order_stats[day].get(person, 0)
        slot_cost = self._day_slot_cost(day, person, item)
        if current_day + slot_cost > daily_limit:
            return False

        # 该日对该专家还是空白日：会新开一个工作日，受每月工作日上限约束
        if current_day == 0 and self._person_workday_count(person) >= self._monthly_workday_limit():
            return False

        week_index = self._get_week_index(day)
        weekly_limit = float(self.cfg.get("MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON", 25.0))
        current_week = self.person_week_order_stats[week_index].get(person, 0.0)
        return current_week + 1 <= weekly_limit + 1e-9

    def _pick_best_day_from_candidates(
        self,
        candidate_days,
        item,
        anchor_day=None,
        used_weeks=None,
        min_gap_days=0,
    ):
        days = sorted({int(day) for day in candidate_days if 1 <= int(day) <= self.days_in_month})
        days = [day for day in days if not self._is_holiday(day)]
        if used_weeks is not None:
            days = [day for day in days if self._get_week_index(day) not in used_weeks]
        if min_gap_days > 0:
            days = [day for day in days if self._check_store_gap_constraint(item, day, min_gap_days)]
        if not days:
            return None, False

        allowed_days, used_relaxed = self._filter_days_by_order_capacity(days, item)
        if not allowed_days:
            return None, used_relaxed
        if anchor_day is None:
            anchor_day = allowed_days[0]
        return self._pick_balanced_day(allowed_days, item, anchor_day), used_relaxed

    def _align_range_window(
        self,
        start_day,
        end_day,
        item,
        enforce_weekly_capacity=False,
        min_gap_days=0,
        preferred_service_day=None,
    ):
        result = super()._align_range_window(
            start_day,
            end_day,
            item,
            enforce_weekly_capacity=False,
            min_gap_days=min_gap_days,
            preferred_service_day=preferred_service_day,
        )
        aligned_start, aligned_end, service_day, adjusted, moved, used_relaxed = result
        if not self._check_person_order_constraint(service_day, item):
            service_day = None
        return aligned_start, aligned_end, service_day, adjusted, moved, used_relaxed

    def _record_conflict(self, start_day, end_day, item, rule_note, reason):
        def as_date(day):
            if day is None:
                return None
            return date(self.cfg["YEAR"], self.cfg["MONTH"], int(day))

        self.conflicts.append(
            {
                "门店ID": item.get("门店ID", ""),
                "门店名称": item.get("门店名称", ""),
                "品牌": item.get("品牌", ""),
                "行政区划": item.get("行政区划", ""),
                self.cfg["SERVICE_PERSON_COL"]: item.get(self.cfg["SERVICE_PERSON_COL"], ""),
                "建议开始日期": as_date(start_day),
                "建议截止日期": as_date(end_day),
                "原排班逻辑": rule_note,
                "异常类型": "硬规则冲突",
                "异常原因": reason,
                "处理状态": "待人工排班",
            }
        )

    def _assign(
        self,
        start_day,
        end_day,
        item,
        rule_note,
        is_fixed=False,
        fixed_day=None,
        remote_day=None,
        load_mode="daily",
    ):
        service_day = remote_day if remote_day is not None else (fixed_day if is_fixed else None)
        if service_day is None:
            preferred = self._get_preferred_days_for_item(item, start_day, end_day, start_day)
            preferred_day = preferred[0] if preferred else start_day + (end_day - start_day) // 2
            service_day, _ = self._pick_service_day_in_window(
                start_day,
                end_day,
                item,
                preferred_day=preferred_day,
                enforce_daily_capacity=True,
            )

        if service_day is None or not self._check_person_order_constraint(service_day, item):
            self._record_conflict(
                start_day,
                end_day,
                item,
                rule_note,
                "可选日期内的人员日容量或周容量已达到上限",
            )
            return False

        occurrences = max(1, round(item.get("clean_freq", 1)))
        minimum_gap = self._get_min_gap_days_for_frequency(
            occurrences,
            is_remote=item.get("行政区划") in self.cfg.get("REMOTE_CITIES", []),
        )
        if not self._check_store_gap_constraint(item, service_day, minimum_gap):
            self._record_conflict(start_day, end_day, item, rule_note, "与同一门店的其他服务日期间隔不足")
            return False

        person = self._get_service_person(item)
        repeated_dorm_group = False
        if person:
            group = self._dorm_group_of(item)
            if group is not None:
                day_groups = self.person_day_slot_groups[service_day][person]
                if group in day_groups:
                    repeated_dorm_group = True
                else:
                    day_groups.add(group)

        super()._assign(
            start_day,
            end_day,
            item,
            rule_note,
            is_fixed=is_fixed,
            fixed_day=fixed_day,
            remote_day=service_day,
            load_mode="daily",
        )
        if person:
            self.person_week_order_stats[self._get_week_index(service_day)][person] += 1
            if repeated_dorm_group:
                # 同一宿舍组当天重复出勤不再额外占用日额度
                self.person_day_order_stats[service_day][person] -= 1
        return True


def _build_runtime_config(config: dict[str, Any]) -> dict[str, Any]:
    runtime = dict(DEFAULT_CONFIG)
    runtime.update(config)
    runtime["HOLIDAY_BLOCKS"] = [tuple(block) for block in runtime.get("HOLIDAY_BLOCKS", [])]
    return runtime


def _iter_geographic_groups(df: pd.DataFrame, config: dict[str, Any]):
    province_column = config.get("PROVINCE_COL", "省份")
    city_column = config.get("CITY_COL", "城市")
    if province_column in df.columns:
        province_groups = df.groupby(province_column, dropna=False, sort=True)
    else:
        province_groups = [("未标注省份", df)]

    for province, province_df in province_groups:
        province_name = str(province).strip() if pd.notna(province) and str(province).strip() else "未标注省份"
        if city_column in province_df.columns:
            city_groups = province_df.groupby(city_column, dropna=False, sort=True)
        else:
            city_groups = [(province_name, province_df)]
        for city, city_df in city_groups:
            city_name = str(city).strip() if pd.notna(city) and str(city).strip() else "未标注城市"
            yield province_name, city_name, city_df


def _expected_occurrences(scheduler: ProductionScheduler, row: pd.Series) -> int:
    frequency = scheduler._clean_parse_freq(row.get(scheduler.cfg["FREQ_COL"]))
    if frequency < 0.1:
        return 0
    if abs(frequency - 0.3) < 0.01:
        last_date = scheduler._parse_date_obj(row.get(scheduler.cfg["LAST_MONTH_COL"]))
        if (
            last_date
            and last_date.year == scheduler.cfg["YEAR"]
            and last_date.month > scheduler.cfg["MONTH"]
        ):
            last_date = last_date.replace(year=scheduler.cfg["YEAR"] - 1)
        item = {"last_date_obj": last_date}
        return 1 if scheduler._should_schedule_quarterly(item) else 0
    return max(1, round(frequency))


def run_schedule(df: pd.DataFrame, config: dict[str, Any]) -> ScheduleRunResult:
    runtime = _build_runtime_config(config)
    days_in_month = ProductionScheduler(runtime).days_in_month
    max_weeks = (days_in_month - 1) // 7 + 1
    shared_capacity = {
        "days": {day: defaultdict(int) for day in range(1, days_in_month + 1)},
        "weeks": {week: defaultdict(float) for week in range(1, max_weeks + 1)},
    }

    result_frames: list[pd.DataFrame] = []
    conflict_frames: list[pd.DataFrame] = []
    expected_total = 0

    for province, city, group in _iter_geographic_groups(df, runtime):
        city_config = dict(runtime)
        city_config["CITY_NAME"] = city
        scheduler = ProductionScheduler(city_config, shared_capacity=shared_capacity)
        expected_total += sum(_expected_occurrences(scheduler, row) for _, row in group.iterrows())
        scheduled = scheduler.run(group)
        if not scheduled.empty:
            scheduled[city_config["PROVINCE_COL"]] = province
            scheduled[city_config["CITY_COL"]] = city
            result_frames.append(scheduled)
        if scheduler.conflicts:
            conflicts = pd.DataFrame(scheduler.conflicts)
            conflicts[city_config["PROVINCE_COL"]] = province
            conflicts[city_config["CITY_COL"]] = city
            conflict_frames.append(conflicts)

    scheduled_df = pd.concat(result_frames, ignore_index=True) if result_frames else pd.DataFrame()
    hard_conflicts = pd.concat(conflict_frames, ignore_index=True) if conflict_frames else pd.DataFrame()

    warnings = pd.DataFrame()
    if not scheduled_df.empty and "排班逻辑" in scheduled_df.columns:
        warning_mask = scheduled_df["排班逻辑"].astype(str).str.contains("[警告:", regex=False)
        if warning_mask.any():
            warning_rows = scheduled_df.loc[warning_mask].copy()
            warnings = pd.DataFrame(
                {
                    "门店ID": warning_rows.get("门店ID", ""),
                    "门店名称": warning_rows.get("门店名称", ""),
                    "品牌": warning_rows.get("品牌", ""),
                    "省份": warning_rows.get(runtime["PROVINCE_COL"], ""),
                    "城市": warning_rows.get(runtime["CITY_COL"], ""),
                    "行政区划": warning_rows.get("行政区划", ""),
                    runtime["SERVICE_PERSON_COL"]: warning_rows.get(runtime["SERVICE_PERSON_COL"], ""),
                    "异常类型": "规则警告",
                    "异常原因": warning_rows["排班逻辑"],
                    "处理状态": "已排但需关注",
                }
            )

    anomalies = pd.concat([frame for frame in (hard_conflicts, warnings) if not frame.empty], ignore_index=True) \
        if (not hard_conflicts.empty or not warnings.empty) else pd.DataFrame()

    scheduled_count = len(scheduled_df)
    hard_conflict_count = len(hard_conflicts)
    missing_count = max(0, expected_total - scheduled_count - hard_conflict_count)
    if missing_count:
        missing = pd.DataFrame(
            [{
                "异常类型": "未生成任务",
                "异常原因": f"有 {missing_count} 条预期服务任务未生成，请检查特殊日期或频次规则",
                "处理状态": "待人工检查",
            }]
        )
        anomalies = pd.concat([anomalies, missing], ignore_index=True)

    summary = {
        "目标月份": f"{int(runtime['YEAR']):04d}-{int(runtime['MONTH']):02d}",
        "输入门店数": len(df),
        "预期服务任务": int(expected_total),
        "成功排班数": int(scheduled_count),
        "硬规则冲突数": int(hard_conflict_count),
        "规则警告数": len(warnings),
        "未生成任务数": int(missing_count),
    }
    return ScheduleRunResult(scheduled=scheduled_df, anomalies=anomalies, summary=summary)
