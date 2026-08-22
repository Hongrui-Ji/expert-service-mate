import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import pandas as pd

# ================= 1. 全局配置中心 (Configuration) =================
DEFAULT_CONFIG = {
    # [时间配置]
    "YEAR": 2026,
    "MONTH": 8,
    
    # [Excel列名映射]（通用名称：不随月份变化）
    "LAST_MONTH_COL": "上月服务日期",
    "FREQ_COL": "本月需要服务次数",
    "SERVICE_PERSON_COL": "服务人员",
    "LAT_COL": "纬度",
    "LNG_COL": "经度",
    "SPECIAL_REQUIREMENT_COL": "特殊要求",
    "LEGACY_SPECIAL_REQUIREMENT_COL": "指定日期",
    
    # [假期配置] 春节: 2/15 ~ 2/21
    "HOLIDAY_BLOCKS": [],

    # [城市配置]
    "CITY_NAME": "",                      # 兼容旧版：单城市模式下使用
    "CITY_COL": "城市",                      # [新增] 省级文件中的城市字段名
    "PROVINCE_COL": "省份",                  # [新增] 合并输入文件中的省份字段名
    "OUTPUT_SPLIT_BY_PROVINCE": True,      # [新增] True时按省份分Sheet输出
    "OUTPUT_SPLIT_BY_CITY":False,          # [兼容] 旧开关，当前多省份方案默认不使用
    "SOFT_ANCHOR_TOLERANCE": 5,            # “上次+30天”软约束容忍天数（±N天）
    # [优化] 补充了昆山等常见周边城市，确保逻辑覆盖
    "REMOTE_CITIES": ['张家港市','太仓市','常熟市',"崇明区","金山区",'慈溪市','瑞安市',"密云区"], 
    
    # [品牌配置]
    "SPECIFIC_DATE_BRANDS": ['嘻游记'], # 指定锁定单日的品牌配置，可自由添加多个
    "SPECIFIC_RANGE_BRANDS": ['塔斯汀中国汉堡',"半天妖烤鱼","GridCoffee","鱼酷活力烤鱼"], # [新增] 指定3天范围的品牌配置（截止锚定上次+30天）

    # [限制配置]
    "MAX_DAILY_ORDERS_PER_PERSON": 2,  # 每位服务人员每天最多2个工单（默认上限）
    "MAX_DAILY_ORDERS_PER_PERSON_RELAXED": 3,  # 排不开时的放宽上限
    "RELAXED_CAP_BEFORE_DAY": 20,  # 仅允许在当月20号（含）之前使用放宽上限
    "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": 6.0,  # 常规/季度按自然周分摊后的每周容量上限
    "NEARBY_ALIGN_RADIUS_METERS": 300,  # 同服务人员下，附近门店尽量同日的默认距离
    "SMOOTHING_ANCHOR_WEIGHT": 10,  # 刚性单平滑：锚点偏离权重
    "SMOOTHING_DAY_LOAD_WEIGHT": 8,  # 刚性单平滑：当日负载权重
    "SMOOTHING_NEIGHBOR_LOAD_WEIGHT": 4,  # 刚性单平滑：相邻日负载权重
    "SMOOTHING_NEARBY_ALIGN_BONUS": 3,  # 刚性单平滑：近邻同日奖励（会从总分里减去）
    "REMOTE_DAILY_PAIR_TARGET": 2,  # 偏远门店同日聚合目标（优先凑到2单/天）
    "REMOTE_MIN_GAP_DAYS_FREQ2": 10,  # 偏远门店频次=2时，同店两次服务最小间隔
    "REMOTE_MIN_GAP_DAYS_FREQ3PLUS": 6,  # 偏远门店频次>=3时，同店相邻两次服务最小间隔
    "REGULAR_MIN_GAP_DAYS_FREQ2": 10,  # 常规/季度门店频次=2时，同店两次服务最小间隔
    "REGULAR_MIN_GAP_DAYS_FREQ3": 7,  # 常规/季度门店频次=3时，同店相邻两次服务最小间隔
    "REGULAR_MIN_GAP_DAYS_FREQ4PLUS": 5,  # 常规/季度门店频次>=4时，同店相邻两次服务最小间隔
    "REMOTE_MAX_SHIFT_DAYS": 3,  # 偏远门店窗口最大顺移天数（相对原起点）
    "BRAND_RANGE_MAX_HOLIDAY_DAYS": 1,  # 3天范围门店窗口内最多允许的假期天数

    # [服务窗口长度] 含首尾自然日天数（如 16 表示从 start 到 start+15 共 16 天）
    "REGULAR_FREQ1_WINDOW_DAYS": 15,   # 每月1次常规/偏远：服务窗口天数
    "QUARTERLY_INTERVAL_MONTHS": 3,    # 季度门店距离上次服务至少满N个月才排
}

# ================= 2. 核心系统逻辑 (System Core) =================

class AutoSchedulerV2:
    def __init__(self, config):
        self.cfg = config
        self.days_in_month = self._get_days_in_month()
        
        self.blocked_days = set()
        for block in self.cfg["HOLIDAY_BLOCKS"]:
            if isinstance(block, (tuple, list)):
                if len(block) == 1:
                    start = end = int(block[0])
                else:
                    start, end = int(block[0]), int(block[1])
            else:
                start = end = int(block)
            for d in range(start, end + 1):
                if d <= self.days_in_month:
                    self.blocked_days.add(d)

        self.person_day_order_stats = {
            d: defaultdict(int)
            for d in range(1, self.days_in_month + 1)
        }
        self.max_weeks = (self.days_in_month - 1) // 7 + 1
        self.person_week_order_stats = {
            w: defaultdict(float)
            for w in range(1, self.max_weeks + 1)
        }
        self.store_service_days = defaultdict(list)
        # 近邻/窗口上下文按服务人员分桶，减少全量扫描与上下文占用
        self.assignment_points_by_person = defaultdict(list)
        self.assignment_windows_by_person = defaultdict(list)
        self.final_schedule = []

    def _get_days_in_month(self):
        if self.cfg["MONTH"] == 12: return 31
        next_month = datetime(self.cfg["YEAR"], self.cfg["MONTH"] + 1, 1)
        return (next_month - timedelta(days=1)).day

    def _is_holiday(self, day):
        return day in self.blocked_days

    def _build_anchor_window(self, anchor_day, span_days):
        span_days = max(1, int(span_days))
        before_days = (span_days - 1) // 2
        after_days = span_days - 1 - before_days
        anchor_day = min(max(1, int(anchor_day)), self.days_in_month)
        start_day = max(1, anchor_day - before_days)
        end_day = min(self.days_in_month, anchor_day + after_days)
        return start_day, end_day

    def _months_since_last_service(self, last_date):
        if not last_date:
            return None
        return (self.cfg["YEAR"] - last_date.year) * 12 + (self.cfg["MONTH"] - last_date.month)

    def _should_schedule_quarterly(self, item):
        months_since = self._months_since_last_service(item.get('last_date_obj'))
        if months_since is None:
            return True
        required_months = int(self.cfg.get("QUARTERLY_INTERVAL_MONTHS", 3))
        return months_since >= required_months

    def _get_alternating_weeks_from_last_date(self, last_date):
        if not last_date:
            return [1, 3]
        last_day = min(max(1, last_date.day), self.days_in_month)
        last_week = self._get_week_index(last_day)
        return [2, 4] if last_week in [2, 4] else [1, 3]

    def _normalize_text(self, value):
        if pd.isna(value):
            return ""
        return str(value).strip()

    def _safe_float(self, value):
        if pd.isna(value) or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_service_person(self, item):
        return self._normalize_text(item.get(self.cfg["SERVICE_PERSON_COL"], ""))

    def _get_coords(self, item):
        lat = self._safe_float(item.get(self.cfg["LAT_COL"]))
        lng = self._safe_float(item.get(self.cfg["LNG_COL"]))
        if lat is None or lng is None:
            return None, None
        return lat, lng

    def _haversine_meters(self, lat1, lng1, lat2, lng2):
        radius = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lng2 - lng1)
        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _is_related_store(self, item, point):
        service_person = self._get_service_person(item)
        if not service_person or service_person != point['service_person']:
            return False

        item_store_id = item.get('门店ID')
        if item_store_id == point.get('store_id'):
            return False

        lat, lng = self._get_coords(item)
        point_lat, point_lng = point.get('lat'), point.get('lng')
        if lat is None or lng is None or point_lat is None or point_lng is None:
            return False

        radius = float(self.cfg.get("NEARBY_ALIGN_RADIUS_METERS", 500))
        return self._haversine_meters(lat, lng, point_lat, point_lng) <= radius

    def _get_related_day_counter(self, item, start_day=1, end_day=None):
        if end_day is None:
            end_day = self.days_in_month

        day_counter = Counter()
        service_person = self._get_service_person(item)
        if not service_person:
            return day_counter

        for point in self.assignment_points_by_person.get(service_person, []):
            service_day = point.get('service_day')
            if service_day is None or service_day < start_day or service_day > end_day:
                continue
            if self._is_related_store(item, point):
                day_counter[service_day] += 1
        return day_counter

    def _merge_preferred_days(self, base_order, preferred_days):
        merged = []
        seen = set()
        for day in preferred_days + base_order:
            if day in seen:
                continue
            seen.add(day)
            merged.append(day)
        return merged

    def _get_preferred_days_for_item(self, item, start_day=1, end_day=None, anchor_day=None):
        if end_day is None:
            end_day = self.days_in_month
        counter = self._get_related_day_counter(item, start_day, end_day)
        if not counter:
            return []

        if anchor_day is None:
            anchor_day = start_day + (end_day - start_day) // 2

        return [
            day for day, _ in sorted(
                counter.items(),
                key=lambda kv: (-kv[1], abs(kv[0] - anchor_day), kv[0])
            )
        ]

    def _build_window_start_order(self, start_day, window_len, item):
        max_start = max(1, self.days_in_month - window_len + 1)
        base_order = []
        seen = set()
        for day in self._build_nearby_day_order(start_day):
            candidate = min(max(1, day), max_start)
            if candidate in seen:
                continue
            seen.add(candidate)
            base_order.append(candidate)

        counter = self._get_related_day_counter(item)
        if not counter:
            return base_order

        preferred = []
        for related_day, _count in sorted(counter.items(), key=lambda kv: (-kv[1], abs(kv[0] - start_day), kv[0])):
            candidates = [
                related_day - window_len // 2,
                related_day - window_len + 1,
                related_day,
            ]
            for candidate in candidates:
                candidate = min(max(1, candidate), max_start)
                preferred.append(candidate)
        return self._merge_preferred_days(preferred, base_order)

    def _get_person_order_count(self, day, item):
        person = self._get_service_person(item)
        return self.person_day_order_stats[day].get(person, 0)

    def _get_neighbor_load(self, day, item):
        prev_load = self._get_person_order_count(day - 1, item) if day - 1 >= 1 else 0
        next_load = self._get_person_order_count(day + 1, item) if day + 1 <= self.days_in_month else 0
        return prev_load + next_load

    def _score_day_with_smoothing(self, day, item, anchor_day=None):
        if anchor_day is None:
            anchor_day = day

        w_anchor = int(self.cfg.get("SMOOTHING_ANCHOR_WEIGHT", 10))
        w_day = int(self.cfg.get("SMOOTHING_DAY_LOAD_WEIGHT", 8))
        w_neighbor = int(self.cfg.get("SMOOTHING_NEIGHBOR_LOAD_WEIGHT", 4))
        nearby_bonus = int(self.cfg.get("SMOOTHING_NEARBY_ALIGN_BONUS", 3))

        nearby_counter = self._get_related_day_counter(item, day, day).get(day, 0)
        score = (
            w_anchor * abs(day - anchor_day)
            + w_day * self._get_person_order_count(day, item)
            + w_neighbor * self._get_neighbor_load(day, item)
            - nearby_bonus * nearby_counter
        )
        return score

    def _sort_days_by_smoothing(self, days, item, anchor_day):
        return sorted(days, key=lambda d: (self._score_day_with_smoothing(d, item, anchor_day), d))

    def _sort_remote_days_for_pairing(self, days, item, anchor_day, target_week=None):
        target = int(self.cfg.get("REMOTE_DAILY_PAIR_TARGET", 2))

        def remote_pair_score(day):
            curr = self._get_person_order_count(day, item)
            if target_week is not None and self._get_week_index(day) != target_week:
                pair_rank = 3  # 跨周时降低配对优先级
            elif curr == target - 1:
                pair_rank = 0  # 优先把当天凑成2单
            elif curr < target - 1:
                pair_rank = 1  # 再选还比较空的日期
            else:
                pair_rank = 2  # 最后才选超过目标聚合的日期
            return (pair_rank, self._score_day_with_smoothing(day, item, anchor_day), day)

        return sorted(days, key=remote_pair_score)

    def _check_store_gap_constraint(self, item, day, min_gap_days):
        if min_gap_days <= 0:
            return True
        store_id = item.get('门店ID')
        if store_id is None:
            return True
        existing_days = self.store_service_days.get(store_id, [])
        for d in existing_days:
            if abs(day - d) < min_gap_days:
                return False
        return True

    def _get_min_gap_days_for_frequency(self, freq, is_remote=False):
        if freq <= 1:
            return 0
        if is_remote:
            if freq == 2:
                return int(self.cfg.get("REMOTE_MIN_GAP_DAYS_FREQ2", 10))
            return int(self.cfg.get("REMOTE_MIN_GAP_DAYS_FREQ3PLUS", 6))
        if freq == 2:
            return int(self.cfg.get("REGULAR_MIN_GAP_DAYS_FREQ2", 10))
        if freq == 3:
            return int(self.cfg.get("REGULAR_MIN_GAP_DAYS_FREQ3", 7))
        return int(self.cfg.get("REGULAR_MIN_GAP_DAYS_FREQ4PLUS", 5))

    def _count_holiday_days_in_range(self, start_day, end_day):
        return sum(1 for d in range(start_day, end_day + 1) if self._is_holiday(d))

    def _build_three_day_window(self, service_day, allowed_days=None):
        allowed_min, allowed_max = 1, self.days_in_month
        if allowed_days:
            valid_allowed_days = sorted({int(d) for d in allowed_days if 1 <= int(d) <= self.days_in_month})
            if valid_allowed_days:
                allowed_min, allowed_max = min(valid_allowed_days), max(valid_allowed_days)

        service_day = min(max(allowed_min, int(service_day)), allowed_max)
        start_day = service_day - 1
        end_day = service_day + 1

        if start_day < allowed_min:
            end_day += allowed_min - start_day
            start_day = allowed_min
        if end_day > allowed_max:
            start_day -= end_day - allowed_max
            end_day = allowed_max

        start_day = max(allowed_min, start_day)
        end_day = min(allowed_max, end_day)
        return start_day, end_day

    def _plan_brand_range_window(self, anchor_day, item, allowed_end_days=None, min_gap_days=0):
        max_holiday_days = int(self.cfg.get("BRAND_RANGE_MAX_HOLIDAY_DAYS", 1))
        candidate_ends = self._build_soft_order(anchor_day, int(self.cfg.get("SOFT_ANCHOR_TOLERANCE", 5)))
        preferred_days = self._get_preferred_days_for_item(item, anchor_day=anchor_day)
        candidate_ends = self._merge_preferred_days(candidate_ends, preferred_days)
        candidate_ends, used_relaxed = self._filter_days_by_order_capacity(candidate_ends, item)
        candidate_ends = self._sort_days_by_smoothing(candidate_ends, item, anchor_day)
        allowed_set = set(allowed_end_days) if allowed_end_days else None

        best_fallback = None
        for service_day in candidate_ends:
            if allowed_set is not None and service_day not in allowed_set:
                continue
            if self._is_holiday(service_day):
                continue
            if min_gap_days > 0 and not self._check_store_gap_constraint(item, service_day, min_gap_days):
                continue
            start_day, end_day = self._build_three_day_window(service_day, allowed_end_days)
            holiday_days = self._count_holiday_days_in_range(start_day, end_day)
            score = (holiday_days, abs(service_day - anchor_day), service_day)

            if best_fallback is None or score < best_fallback[0]:
                best_fallback = (score, start_day, end_day, service_day, used_relaxed)

            if holiday_days <= max_holiday_days:
                return start_day, end_day, service_day, holiday_days, used_relaxed, False

        if best_fallback is not None:
            _, start_day, end_day, service_day, used_relaxed_fallback = best_fallback
            holiday_days = self._count_holiday_days_in_range(start_day, end_day)
            return start_day, end_day, service_day, holiday_days, used_relaxed_fallback, True

        if allowed_set:
            fallback_candidates = sorted(allowed_set, key=lambda d: (abs(d - anchor_day), d))
            fallback_service_day = next(
                (
                    d for d in fallback_candidates
                    if (not self._is_holiday(d))
                    and (min_gap_days <= 0 or self._check_store_gap_constraint(item, d, min_gap_days))
                ),
                None
            )
            if fallback_service_day is None:
                fallback_service_day = next((d for d in fallback_candidates if not self._is_holiday(d)), fallback_candidates[0])
            fallback_start, fallback_end = self._build_three_day_window(fallback_service_day, allowed_end_days)
            holiday_days = self._count_holiday_days_in_range(fallback_start, fallback_end)
            return fallback_start, fallback_end, fallback_service_day, holiday_days, used_relaxed, holiday_days > max_holiday_days

        fallback_service_day = min(max(1, anchor_day), self.days_in_month)
        if min_gap_days > 0 and not self._check_store_gap_constraint(item, fallback_service_day, min_gap_days):
            for day in range(1, self.days_in_month + 1):
                if self._is_holiday(day):
                    continue
                if self._check_store_gap_constraint(item, day, min_gap_days):
                    fallback_service_day = day
                    break
        fallback_start, fallback_end = self._build_three_day_window(fallback_service_day, allowed_end_days)
        holiday_days = self._count_holiday_days_in_range(fallback_start, fallback_end)
        return fallback_start, fallback_end, fallback_service_day, holiday_days, False, True

    def _get_specified_brand_range_limit(self, item):
        rule = item.get('specified_date_rule') or {'mode': 'none'}
        mode = rule.get('mode')
        if mode == 'date_range':
            start_day = max(1, int(rule.get('start_day', 1)))
            end_day = min(self.days_in_month, int(rule.get('end_day', self.days_in_month)))
            allowed_end_days = [
                day for day in range(start_day, end_day + 1)
                if 1 <= day <= self.days_in_month
            ]
            return allowed_end_days, f"-特殊范围{start_day}至{end_day}号"

        if mode == 'candidate_dates':
            allowed_end_days = [
                dt.day for dt in rule.get('dates', [])
                if dt.month == self.cfg["MONTH"] and dt.year == self.cfg["YEAR"]
            ]
            if allowed_end_days:
                return sorted(set(allowed_end_days)), "-特殊候选日"

        return None, ""

    def _get_week_index(self, day):
        return (day - 1) // 7 + 1

    def _get_window_week_shares(self, start_day, end_day):
        total_days = max(1, end_day - start_day + 1)
        by_week = defaultdict(int)
        for day in range(start_day, end_day + 1):
            by_week[self._get_week_index(day)] += 1
        return {week_idx: cnt / total_days for week_idx, cnt in by_week.items()}

    def _check_person_week_capacity(self, start_day, end_day, item):
        person = self._get_service_person(item)
        if not person:
            return True
        cap = float(self.cfg.get("MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON", 6.0))
        shares = self._get_window_week_shares(start_day, end_day)
        for week_idx, weight in shares.items():
            curr = self.person_week_order_stats[week_idx].get(person, 0.0)
            if curr + weight > cap + 1e-9:
                return False
        return True

    def _check_person_order_constraint(self, day, item, allow_relaxed=False):
        person = self._get_service_person(item)
        if not person:
            return True

        strict_limit = int(self.cfg.get("MAX_DAILY_ORDERS_PER_PERSON", 2))
        relaxed_limit = int(self.cfg.get("MAX_DAILY_ORDERS_PER_PERSON_RELAXED", 3))
        relaxed_before_day = int(self.cfg.get("RELAXED_CAP_BEFORE_DAY", 20))
        curr_count = self._get_person_order_count(day, item)

        if curr_count < strict_limit:
            return True
        if allow_relaxed and day <= relaxed_before_day and curr_count < relaxed_limit:
            return True
        return False

    def _filter_days_by_order_capacity(self, days, item):
        strict_days = [d for d in days if self._check_person_order_constraint(d, item, allow_relaxed=False)]
        if strict_days:
            return strict_days, False
        relaxed_days = [d for d in days if self._check_person_order_constraint(d, item, allow_relaxed=True)]
        return relaxed_days, True

    def _pick_service_day_in_window(self, start_day, end_day, item, preferred_day=None, enforce_daily_capacity=True, min_gap_days=0):
        day_order = self._build_window_day_order(start_day, end_day, preferred_day)
        day_order = [d for d in day_order if not self._is_holiday(d)]
        if min_gap_days > 0:
            day_order = [d for d in day_order if self._check_store_gap_constraint(item, d, min_gap_days)]
        if not day_order:
            return None, False

        if not enforce_daily_capacity:
            return day_order[0], False

        allowed_days, used_relaxed = self._filter_days_by_order_capacity(day_order, item)
        if not allowed_days:
            return None, used_relaxed
        return allowed_days[0], used_relaxed

    def _register_assignment_point(self, item, service_day):
        service_person = self._get_service_person(item)
        if not service_person:
            return
        lat, lng = self._get_coords(item)
        self.assignment_points_by_person[service_person].append({
            'store_id': item.get('门店ID'),
            'service_person': service_person,
            'lat': lat,
            'lng': lng,
            'service_day': service_day,
        })

    def _register_assignment_window(self, item, start_day, end_day):
        service_person = self._get_service_person(item)
        if not service_person:
            return
        lat, lng = self._get_coords(item)
        self.assignment_windows_by_person[service_person].append({
            'store_id': item.get('门店ID'),
            'service_person': service_person,
            'lat': lat,
            'lng': lng,
            'start_day': int(start_day),
            'end_day': int(end_day),
        })

    def _append_remote_tag(self, note, item):
        if item.get('行政区划') in self.cfg.get("REMOTE_CITIES", []):
            if "偏远门店" not in note:
                return note + "-偏远门店"
        return note

    def _windows_overlap(self, start1, end1, start2, end2):
        return max(start1, start2) <= min(end1, end2)

    def _get_related_window_overlap_count(self, item, start_day, end_day):
        count = 0
        service_person = self._get_service_person(item)
        if not service_person:
            return count

        for win in self.assignment_windows_by_person.get(service_person, []):
            if not self._is_related_store(item, win):
                continue
            if self._windows_overlap(start_day, end_day, win['start_day'], win['end_day']):
                count += 1
        return count

    def _clean_parse_freq(self, val):
        """
        [新增] 强力清洗频次数据
        解决 "4 ", "2.0", "4次" 等格式问题
        """
        if pd.isna(val): return 0.0
        val_str = str(val).strip()
        # 使用正则提取第一个数字（包括小数）
        match = re.search(r'(\d+(\.\d+)?)', val_str)
        if match:
            return float(match.group(1))
        return 0.0

    def _adjust_range_for_holiday(self, start_day, end_day):
        valid_days = [d for d in range(start_day, end_day + 1) if not self._is_holiday(d)]
        if valid_days:
            return min(valid_days), max(valid_days), False
        else:
            duration = end_day - start_day
            new_start = end_day + 1
            while self._is_holiday(new_start) and new_start <= self.days_in_month:
                new_start += 1
            
            if new_start <= self.days_in_month:
                new_end = min(new_start + duration, self.days_in_month)
                return new_start, new_end, True
            else:
                new_end = start_day - 1
                while self._is_holiday(new_end) and new_end >= 1:
                    new_end -= 1
                new_start = max(1, new_end - duration)
                return new_start, new_end, True

    def _parse_date_obj(self, date_val):
        if pd.isna(date_val) or date_val == '': return None
        if isinstance(date_val, pd.Timestamp): return date_val.to_pydatetime()
        if isinstance(date_val, datetime): return date_val
        date_str = str(date_val).strip()
        full_formats = ["%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d", "%m/%d/%Y"]
        for fmt in full_formats:
            try: return datetime.strptime(date_str, fmt)
            except ValueError: continue
        separators = ['/', '-', '.']
        for sep in separators:
            if sep in date_str:
                try:
                    full_date_str = f"{self.cfg['YEAR']}{sep}{date_str}"
                    return datetime.strptime(full_date_str, f"%Y{sep}%m{sep}%d")
                except ValueError: continue
        return None

    def _parse_dates_list(self, date_val):
        if pd.isna(date_val) or date_val == '': return []
        results = []
        date_str = str(date_val).strip()
        
        cn_weekdays = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}
        matches_week = re.findall(r'(?:周|星期)([一二三四五六日天])', date_str)
        if matches_week:
            for cn_w in matches_week:
                wd_idx = cn_weekdays.get(cn_w)
                for day in range(1, self.days_in_month + 1):
                    dt = datetime(self.cfg['YEAR'], self.cfg['MONTH'], day)
                    if dt.weekday() == wd_idx:
                        results.append(dt)
            if results: return sorted(list(set(results)))

        if '号' in date_str or '日' in date_str:
            matches_full = re.findall(r'(\d+)[月\.\-\/](\d+)[号日]', date_str)
            for m in matches_full:
                try: results.append(datetime(self.cfg['YEAR'], int(m[0]), int(m[1])))
                except: pass
            if not results:
                matches_day = re.findall(r'(\d+)[号日]', date_str)
                for d_str in matches_day:
                    try: results.append(datetime(self.cfg['YEAR'], self.cfg['MONTH'], int(d_str)))
                    except: pass
            if results: return results

        temp_str = date_str.replace('，', ',').replace('、', ',').replace('；', ',').replace(' / ', ',')
        parts = temp_str.split(',')
        for p in parts:
            p = p.strip()
            if not p: continue
            dt = self._parse_date_obj(p)
            if dt: results.append(dt)
        return results

    def _cn_num_to_int(self, value):
        text = str(value).strip()
        if text.isdigit():
            return int(text)
        mapping = {
            '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        }
        if text in mapping:
            return mapping[text]
        if text.startswith('十') and len(text) == 2:
            return 10 + mapping.get(text[1], 0)
        if text.endswith('十') and len(text) == 2:
            return mapping.get(text[0], 0) * 10
        if '十' in text:
            left, right = text.split('十', 1)
            return mapping.get(left, 1) * 10 + mapping.get(right, 0)
        return None

    def _extract_time_note(self, text):
        notes = []
        for note in ['凌晨', '早上', '上午', '中午', '下午', '晚上', '夜间']:
            if note in text:
                notes.append(note)
        return '、'.join(notes)

    def _weekday_dates(self, weekday_idx, start_day=1, end_day=None):
        if end_day is None:
            end_day = self.days_in_month
        dates = []
        for day in range(max(1, start_day), min(self.days_in_month, end_day) + 1):
            dt = datetime(self.cfg['YEAR'], self.cfg['MONTH'], day)
            if dt.weekday() == weekday_idx:
                dates.append(dt)
        return dates

    def _parse_specified_date_rule(self, date_val):
        if pd.isna(date_val) or str(date_val).strip() == '':
            return {'mode': 'none', 'raw': ''}

        raw = str(date_val).strip()
        text = raw.replace(' ', '').replace('，', '、').replace(',', '、')
        time_note = self._extract_time_note(text)
        cn_weekdays = {'一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6}

        # 例：每月第二周第四周周五晚上
        week_nums = [
            self._cn_num_to_int(token)
            for token in re.findall(r'第([一二两三四五六七八九十\d]+)周', text)
        ]
        week_nums = [n for n in week_nums if n is not None]
        weekday_tokens = re.findall(r'(?:周|星期)([一二三四五六日天])', text)
        if week_nums and weekday_tokens:
            dates = []
            for week_no in week_nums:
                week_start = (week_no - 1) * 7 + 1
                week_end = min(week_start + 6, self.days_in_month)
                for token in weekday_tokens:
                    dates.extend(self._weekday_dates(cn_weekdays[token], week_start, week_end))
            return {
                'mode': 'fixed_dates',
                'dates': sorted(set(dates)),
                'raw': raw,
                'time_note': time_note,
                'source_type': 'week_number_weekday',
            }

        # 例：1到20号、1-20号、1~20号
        range_match = re.search(r'(\d{1,2})(?:号|日)?(?:到|至|\-|~|—)(\d{1,2})(?:号|日)?', text)
        if range_match:
            start_day = max(1, int(range_match.group(1)))
            end_day = min(self.days_in_month, int(range_match.group(2)))
            if start_day > end_day:
                start_day, end_day = end_day, start_day
            return {
                'mode': 'date_range',
                'start_day': start_day,
                'end_day': end_day,
                'raw': raw,
                'time_note': time_note,
                'source_type': 'day_range',
            }

        # 例：3号之前。业务口径：包含3号。
        before_match = re.search(r'(\d{1,2})(?:号|日)?(?:之前|以前|前)', text)
        if before_match:
            end_day = min(self.days_in_month, int(before_match.group(1)))
            return {
                'mode': 'date_range',
                'start_day': 1,
                'end_day': end_day,
                'raw': raw,
                'time_note': time_note,
                'source_type': 'before_day_inclusive',
            }

        # 例：周二或周三、周二到周三。表示每周这些星期都是候选日，多次服务需落在不同周。
        weekday_range_match = re.search(r'(?:周|星期)([一二三四五六日天])(?:到|至|\-|~|—)(?:周|星期)?([一二三四五六日天])', text)
        is_weekday_choice = ('或' in text or weekday_range_match is not None or len(set(weekday_tokens)) >= 2) and len(weekday_tokens) >= 2
        if weekday_range_match:
            start_idx = cn_weekdays[weekday_range_match.group(1)]
            end_idx = cn_weekdays[weekday_range_match.group(2)]
            if start_idx <= end_idx:
                weekday_idxs = list(range(start_idx, end_idx + 1))
            else:
                weekday_idxs = list(range(start_idx, 7)) + list(range(0, end_idx + 1))
        else:
            weekday_idxs = [cn_weekdays[token] for token in weekday_tokens]

        if is_weekday_choice:
            dates = []
            for weekday_idx in weekday_idxs:
                dates.extend(self._weekday_dates(weekday_idx))
            return {
                'mode': 'candidate_dates',
                'dates': sorted(set(dates)),
                'raw': raw,
                'time_note': time_note,
                'source_type': 'weekday_choice',
                'require_different_weeks': True,
            }

        # 例：每周一、每周三。继续按明确日期处理。
        if weekday_tokens:
            dates = []
            for token in weekday_tokens:
                dates.extend(self._weekday_dates(cn_weekdays[token]))
            return {
                'mode': 'fixed_dates',
                'dates': sorted(set(dates)),
                'raw': raw,
                'time_note': time_note,
                'source_type': 'weekly_fixed',
            }

        dates = [
            dt for dt in self._parse_dates_list(raw)
            if dt.month == self.cfg["MONTH"] and dt.year == self.cfg["YEAR"]
        ]
        if dates:
            return {
                'mode': 'fixed_dates',
                'dates': sorted(set(dates)),
                'raw': raw,
                'time_note': time_note,
                'source_type': 'explicit_dates',
            }

        return {
            'mode': 'unrecognized',
            'raw': raw,
            'time_note': time_note,
            'warning': '无法识别特殊要求',
        }

    def _get_needed_occurrences(self, item):
        freq_num = item.get('clean_freq', 0)
        return max(1, int(round(freq_num))) if freq_num >= 1 else 1

    def _get_target_weeks_for_occurrences(self, item, occurrences):
        last_date = item.get('last_date_obj')
        if occurrences == 2:
            return self._get_alternating_weeks_from_last_date(last_date)
        if occurrences >= 4:
            return [1, 2, 3, 4][:occurrences]
        return list(range(1, min(self.max_weeks, occurrences) + 1))

    def _pick_best_day_from_candidates(self, candidate_days, item, anchor_day=None, used_weeks=None, min_gap_days=0):
        days = sorted({int(d) for d in candidate_days if 1 <= int(d) <= self.days_in_month})
        days = [d for d in days if not self._is_holiday(d)]
        if used_weeks is not None:
            days = [d for d in days if self._get_week_index(d) not in used_weeks]
        if min_gap_days > 0:
            days = [d for d in days if self._check_store_gap_constraint(item, d, min_gap_days)]
        if not days:
            return None, False

        strict_days = [d for d in days if self._check_person_order_constraint(d, item, allow_relaxed=False)]
        used_relaxed = False
        if not strict_days:
            relaxed_days = [d for d in days if self._check_person_order_constraint(d, item, allow_relaxed=True)]
            if relaxed_days:
                strict_days = relaxed_days
                used_relaxed = True
            else:
                strict_days = days
        if anchor_day is None:
            anchor_day = strict_days[0]
        sorted_days = self._sort_days_by_smoothing(strict_days, item, anchor_day)
        return sorted_days[0] if sorted_days else None, used_relaxed

    def _resolve_specified_rule_days(self, item):
        rule = item.get('specified_date_rule') or {'mode': 'none'}
        needed = self._get_needed_occurrences(item)
        mode = rule.get('mode')
        time_note = rule.get('time_note')
        extra_note = f"-{time_note}" if time_note else ""

        if mode == 'fixed_dates':
            days = [
                dt.day for dt in rule.get('dates', [])
                if dt.month == self.cfg["MONTH"] and dt.year == self.cfg["YEAR"]
            ]
            days = sorted(set(days))[:needed]
            return [(day, day, day, False, extra_note) for day in days]

        if mode in {'candidate_dates', 'date_range'}:
            if mode == 'candidate_dates':
                candidate_days = [
                    dt.day for dt in rule.get('dates', [])
                    if dt.month == self.cfg["MONTH"] and dt.year == self.cfg["YEAR"]
                ]
                base_note = "-候选星期"
            else:
                candidate_days = list(range(rule.get('start_day', 1), rule.get('end_day', self.days_in_month) + 1))
                base_note = f"-候选范围{rule.get('start_day', 1)}至{rule.get('end_day', self.days_in_month)}号"

            selected = []
            used_weeks = set()
            target_weeks = self._get_target_weeks_for_occurrences(item, needed)
            require_different_weeks = bool(rule.get('require_different_weeks')) or needed > 1
            min_gap_days = self._get_min_gap_days_for_frequency(needed)

            for idx in range(needed):
                week_candidates = candidate_days
                anchor_day = None
                selected_anchor_days = [entry[2] for entry in selected]
                if idx < len(target_weeks):
                    week_no = target_weeks[idx]
                    week_start = (week_no - 1) * 7 + 1
                    week_end = min(week_start + 6, self.days_in_month)
                    week_candidates = [d for d in candidate_days if week_start <= d <= week_end]
                    anchor_day = week_start
                if min_gap_days > 0 and selected_anchor_days:
                    week_candidates = [
                        d for d in week_candidates
                        if all(abs(d - selected_day) >= min_gap_days for selected_day in selected_anchor_days)
                    ]

                day, used_relaxed = self._pick_best_day_from_candidates(
                    week_candidates,
                    item,
                    anchor_day=anchor_day,
                    used_weeks=used_weeks if require_different_weeks else None,
                    min_gap_days=min_gap_days,
                )
                if day is None:
                    fallback_candidates = candidate_days
                    if min_gap_days > 0 and selected_anchor_days:
                        fallback_candidates = [
                            d for d in fallback_candidates
                            if all(abs(d - selected_day) >= min_gap_days for selected_day in selected_anchor_days)
                        ]
                    day, used_relaxed = self._pick_best_day_from_candidates(
                        fallback_candidates,
                        item,
                        used_weeks=used_weeks if require_different_weeks else None,
                        min_gap_days=min_gap_days,
                    )
                if day is None:
                    break
                if mode == 'candidate_dates' and rule.get('source_type') == 'weekday_choice':
                    week_no = self._get_week_index(day)
                    range_days = [d for d in candidate_days if self._get_week_index(d) == week_no]
                    start_day = min(range_days) if range_days else day
                    end_day = max(range_days) if range_days else day
                    selected.append((start_day, end_day, day, used_relaxed, base_note + extra_note))
                elif mode == 'date_range':
                    start_day = rule.get('start_day', 1)
                    end_day = rule.get('end_day', self.days_in_month)
                    selected.append((start_day, end_day, day, used_relaxed, base_note + extra_note))
                else:
                    selected.append((day, day, day, used_relaxed, base_note + extra_note))
                if require_different_weeks:
                    used_weeks.add(self._get_week_index(day))

            return selected

        return []

    def _build_nearby_day_order(self, anchor_day):
        anchor_day = min(max(1, int(anchor_day)), self.days_in_month)
        search_order = [anchor_day]
        for offset in range(1, self.days_in_month):
            if anchor_day + offset <= self.days_in_month:
                search_order.append(anchor_day + offset)
            if anchor_day - offset >= 1:
                search_order.append(anchor_day - offset)
        return search_order

    def _find_best_slot(self, target_day, is_fixed_type, is_remote, item=None):
        while self._is_holiday(target_day):
            target_day += 1
            if target_day > self.days_in_month: target_day = 1 
            
        search_order = self._build_nearby_day_order(target_day)
        if item is not None:
            preferred_days = self._get_preferred_days_for_item(item, anchor_day=target_day)
            search_order = self._merge_preferred_days(search_order, preferred_days)

        if item is not None:
            search_order, _ = self._filter_days_by_order_capacity(search_order, item)
            if is_remote:
                search_order = self._sort_remote_days_for_pairing(search_order, item, target_day)
            else:
                search_order = self._sort_days_by_smoothing(search_order, item, target_day)
            
        for day in search_order:
            if self._is_holiday(day): continue
            valid = True
            if valid: return day
        return target_day

    def _get_brand_anchor_day(self, last_date):
        if not last_date:
            return 1
        return min(max(1, last_date.day), self.days_in_month)

    def _build_soft_order(self, anchor_day, tolerance):
        days = list(range(1, self.days_in_month + 1))
        in_band = [d for d in days if abs(d - anchor_day) <= tolerance]
        out_band = [d for d in days if abs(d - anchor_day) > tolerance]
        # 同距离时优先更早日期（由“偏晚”改为“偏早”）
        in_band.sort(key=lambda d: (abs(d - anchor_day), d))
        out_band.sort(key=lambda d: (abs(d - anchor_day), d))
        return in_band + out_band

    def _find_best_slot_soft(self, anchor_day, is_fixed_type, is_remote, item=None):
        tolerance = int(self.cfg.get("SOFT_ANCHOR_TOLERANCE", 5))
        search_order = self._build_soft_order(anchor_day, tolerance)
        if item is not None:
            preferred_days = self._get_preferred_days_for_item(item, anchor_day=anchor_day)
            search_order = self._merge_preferred_days(search_order, preferred_days)
            search_order, _ = self._filter_days_by_order_capacity(search_order, item)
            if is_remote:
                search_order = self._sort_remote_days_for_pairing(search_order, item, anchor_day)
            else:
                search_order = self._sort_days_by_smoothing(search_order, item, anchor_day)
        for day in search_order:
            if self._is_holiday(day):
                continue
            valid = True
            if valid:
                return day
        return anchor_day

    def _build_window_day_order(self, start_day, end_day, preferred_day=None):
        if preferred_day is None:
            preferred_day = start_day + (end_day - start_day) // 2
        preferred_day = min(max(start_day, int(preferred_day)), end_day)

        search_order = []
        seen = set()
        for day in self._build_nearby_day_order(preferred_day):
            if day < start_day or day > end_day or day in seen:
                continue
            seen.add(day)
            search_order.append(day)
        return search_order

    def _find_remote_day_in_window(self, start_day, end_day, preferred_day=None):
        for day in self._build_window_day_order(start_day, end_day, preferred_day):
            if self._is_holiday(day):
                continue
            return day
        return None

    def _align_range_window(self, start_day, end_day, item, enforce_weekly_capacity=False, min_gap_days=0, allow_window_shift=True, preferred_service_day=None):
        window_len = end_day - start_day + 1
        anchor_day = preferred_service_day if preferred_service_day is not None else start_day + (end_day - start_day) // 2
        anchor_day = min(max(start_day, int(anchor_day)), end_day)
        best_candidate = None

        capacity_modes = [False, True] if enforce_weekly_capacity else [False]
        for relaxed_week_capacity in capacity_modes:
            candidate_starts = self._build_window_start_order(start_day, window_len, item) if allow_window_shift else [start_day]
            for candidate_start in candidate_starts:
                candidate_end = candidate_start + window_len - 1
                if (
                    enforce_weekly_capacity
                    and not relaxed_week_capacity
                    and not self._check_person_week_capacity(candidate_start, candidate_end, item)
                ):
                    continue
                service_day, used_relaxed = self._pick_service_day_in_window(
                    candidate_start,
                    candidate_end,
                    item,
                    preferred_day=min(max(candidate_start, anchor_day), candidate_end),
                    enforce_daily_capacity=not enforce_weekly_capacity,
                    min_gap_days=min_gap_days,
                )
                if service_day is None:
                    continue
                overlap_count = self._get_related_window_overlap_count(item, candidate_start, candidate_end)
                score = (
                    1 if relaxed_week_capacity else 0,  # 周容量不够时可放宽，但排在严格可行方案之后
                    abs(candidate_start - start_day),  # 优先保持原业务窗口
                    self._score_day_with_smoothing(service_day, item, anchor_day),  # 再考虑负载与锚点偏离
                    -overlap_count,  # 近邻对齐仅作为同等条件下的最后加分
                    candidate_start,
                    service_day,
                )
                candidate = (score, candidate_start, candidate_end, service_day, used_relaxed, overlap_count)
                if best_candidate is None or candidate < best_candidate:
                    best_candidate = candidate

        if best_candidate is None:
            fallback_day, used_relaxed = self._pick_service_day_in_window(
                start_day,
                end_day,
                item,
                preferred_day=anchor_day,
                enforce_daily_capacity=not enforce_weekly_capacity,
                min_gap_days=min_gap_days,
            )
            if fallback_day is None:
                return start_day, end_day, start_day, False, False, False
            return start_day, end_day, fallback_day, False, False, used_relaxed

        _, aligned_start, aligned_end, service_day, used_relaxed, _overlap_count = best_candidate
        moved = aligned_start != start_day or aligned_end != end_day
        return aligned_start, aligned_end, service_day, False, moved, used_relaxed

    def _plan_remote_window(self, start_day, end_day, item, min_gap_days=0, allow_window_shift=True):
        original_start, original_end = start_day, end_day
        window_len = end_day - start_day + 1
        max_shift = int(self.cfg.get("REMOTE_MAX_SHIFT_DAYS", 3))
        min_allowed_start = max(1, original_start - max_shift)
        max_allowed_start = min(max(1, self.days_in_month - window_len + 1), original_start + max_shift)
        target_week = self._get_week_index(start_day)

        candidate_starts = self._build_window_start_order(start_day, window_len, item) if allow_window_shift else [start_day]
        for candidate_start in candidate_starts:
            if candidate_start < min_allowed_start or candidate_start > max_allowed_start:
                continue
            candidate_end = candidate_start + window_len - 1
            adjusted_start, adjusted_end, holiday_adjusted = self._adjust_range_for_holiday(candidate_start, candidate_end)
            preferred_days = self._get_preferred_days_for_item(item, adjusted_start, adjusted_end, start_day)
            preferred_day = preferred_days[0] if preferred_days else min(max(adjusted_start, candidate_start), adjusted_end)
            candidate_days = self._build_window_day_order(adjusted_start, adjusted_end, preferred_day)
            candidate_days = [d for d in candidate_days if not self._is_holiday(d)]
            candidate_days, used_relaxed = self._filter_days_by_order_capacity(candidate_days, item)
            candidate_days = [d for d in candidate_days if self._check_store_gap_constraint(item, d, min_gap_days)]
            candidate_days = self._sort_remote_days_for_pairing(candidate_days, item, preferred_day, target_week=target_week)
            remote_day = candidate_days[0] if candidate_days else None
            if remote_day is not None:
                moved = adjusted_start != original_start or adjusted_end != original_end
                return adjusted_start, adjusted_end, remote_day, holiday_adjusted, moved, used_relaxed

        adjusted_start, adjusted_end, holiday_adjusted = self._adjust_range_for_holiday(start_day, end_day)
        fallback_candidates = [d for d in range(adjusted_start, adjusted_end + 1) if not self._is_holiday(d)]
        fallback_candidates, used_relaxed = self._filter_days_by_order_capacity(fallback_candidates, item)
        fallback_candidates = [d for d in fallback_candidates if self._check_store_gap_constraint(item, d, min_gap_days)]
        fallback_candidates = self._sort_remote_days_for_pairing(fallback_candidates, item, start_day, target_week=target_week)
        fallback_remote_day = fallback_candidates[0] if fallback_candidates else min(max(1, adjusted_start), self.days_in_month)
        return adjusted_start, adjusted_end, fallback_remote_day, holiday_adjusted, False, used_relaxed

    def _assign(self, start_day, end_day, item, rule_note, is_fixed=False, fixed_day=None, remote_day=None, load_mode="daily"):
        """
        fixed_day:
          - 当 is_fixed=True 时，用于标记固定类工单的服务锚点日期。
          - 默认沿用 start_day（保持旧逻辑不变）。
          - 3天范围品牌可用 end_day 作为服务锚点，以减少重叠窗口造成的排不开问题。

        remote_day:
          - 偏远范围单会在窗口内挑选一个服务锚点日期（用于对齐与统计）。
        """
        if item.get('specified_date_warning') and item['specified_date_warning'] not in rule_note:
            rule_note += f"[警告:{item['specified_date_warning']}]"

        cap_day = fixed_day if is_fixed else None
        service_day = remote_day if remote_day is not None else cap_day
        if service_day is None:
            preferred_days = self._get_preferred_days_for_item(item, start_day, end_day, start_day)
            service_day = preferred_days[0] if preferred_days else start_day + (end_day - start_day) // 2

        person = self._get_service_person(item)
        if person:
            if load_mode == "weekly":
                for week_idx, weight in self._get_window_week_shares(start_day, end_day).items():
                    self.person_week_order_stats[week_idx][person] += weight
            else:
                self.person_day_order_stats[service_day][person] += 1
        store_id = item.get('门店ID')
        if store_id is not None:
            self.store_service_days[store_id].append(service_day)
        self._register_assignment_point(item, service_day)
        self._register_assignment_window(item, start_day, end_day)
        
        # 使用真正的日期类型写入Excel，避免文本排序问题
        s_dt = datetime(self.cfg['YEAR'], self.cfg['MONTH'], start_day).date()
        e_dt = datetime(self.cfg['YEAR'], self.cfg['MONTH'], end_day).date()
        interval = "N/A"
        if item.get('last_date_obj'):
            curr_date = datetime(self.cfg['YEAR'], self.cfg['MONTH'], start_day)
            interval = (curr_date - item['last_date_obj']).days

        window_days = end_day - start_day + 1
        self.final_schedule.append({
            '门店ID': item['门店ID'],
            '门店名称': item['门店名称'],
            '品牌': item['品牌'],
            '行政区划': item['行政区划'],
            self.cfg["SERVICE_PERSON_COL"]: item.get(self.cfg["SERVICE_PERSON_COL"], ''),
            self.cfg["LAT_COL"]: item.get(self.cfg["LAT_COL"], ''),
            self.cfg["LNG_COL"]: item.get(self.cfg["LNG_COL"], ''),
            '开始日期': s_dt,
            '截止日期': e_dt,
            '服务窗口时长': window_days,
            '服务锚点日期': datetime(self.cfg['YEAR'], self.cfg['MONTH'], service_day).date(),
            '上月服务日期': item.get(self.cfg['LAST_MONTH_COL'], ''), 
            '距离上月间隔': interval,
            '排班逻辑': rule_note
        })

    def _assign_range(self, item, prefix="常规", is_remote=False):
        """ [新增] 抽取常规的范围区间排班逻辑，供普通和偏远门店复用 """
        freq = int(item['clean_freq'])
        last_date = item['last_date_obj']

        def finalize_range(start_day, end_day, note, adjusted=False, allow_window_shift=True, preferred_service_day=None):
            final_start, final_end = start_day, end_day
            final_note = self._append_remote_tag(note, item) + ("-假期避让" if adjusted else "")
            remote_day = None
            service_day = None
            min_gap_days = self._get_min_gap_days_for_frequency(freq, is_remote=is_remote)
            if is_remote:
                final_start, final_end, remote_day, holiday_adjusted_remote, moved, used_relaxed = self._plan_remote_window(
                    start_day, end_day, item, min_gap_days=min_gap_days, allow_window_shift=allow_window_shift
                )
                if holiday_adjusted_remote and "-假期避让" not in final_note:
                    final_note += "-假期避让"
                if moved:
                    final_note += "-偏远顺移"
                if used_relaxed:
                    final_note += "-20日前放宽3单"
                final_note += f"-偏远占用日{remote_day}号"
                self._assign(final_start, final_end, item, final_note, remote_day=remote_day, load_mode="daily")
            else:
                final_start, final_end, service_day, holiday_adjusted_align, moved, _used_relaxed = self._align_range_window(
                    start_day,
                    end_day,
                    item,
                    enforce_weekly_capacity=True,
                    min_gap_days=min_gap_days,
                    allow_window_shift=allow_window_shift,
                    preferred_service_day=preferred_service_day,
                )
                if holiday_adjusted_align and "-假期避让" not in final_note:
                    final_note += "-假期避让"
                if moved and self._get_related_day_counter(item):
                    final_note += "-近邻对齐"
                self._assign(final_start, final_end, item, final_note, remote_day=service_day, load_mode="weekly")

        if freq == 1:
            span = int(self.cfg.get("REGULAR_FREQ1_WINDOW_DAYS", 16))
            span = max(1, span)
            preferred_service_day = None
            if last_date:
                preferred_service_day = min(max(1, last_date.day), self.days_in_month)
                s_day, e_day = self._build_anchor_window(preferred_service_day, span)
            else:
                s_day, e_day = 1, min(span, self.days_in_month)
            
            s_day, e_day, adjusted = self._adjust_range_for_holiday(s_day, e_day)
            finalize_range(
                s_day,
                e_day,
                f"{prefix}-第1次",
                adjusted,
                allow_window_shift=False,
                preferred_service_day=preferred_service_day,
            )

        elif freq == 2:
            weeks = self._get_alternating_weeks_from_last_date(last_date)

            for idx, w in enumerate(weeks, start=1):
                s_day = (w-1)*7 + 1
                e_day = min(s_day + 6, self.days_in_month)
                
                is_full_holiday = all(self._is_holiday(d) for d in range(s_day, e_day + 1))
                s_day, e_day, adjusted = self._adjust_range_for_holiday(s_day, e_day)
                
                note = f"{prefix}-第{idx}次"
                if is_full_holiday: note += "[原定周全休-顺延]"
                finalize_range(s_day, e_day, note, adjusted and not is_full_holiday, allow_window_shift=False)

        elif freq == 3:
            periods = [
                (1, min(10, self.days_in_month)),
                (11, min(20, self.days_in_month)),
                (21, self.days_in_month),
            ]
            for idx, (s_day, e_day) in enumerate(periods, start=1):
                if s_day > self.days_in_month:
                    break
                s_day, e_day, adjusted = self._adjust_range_for_holiday(s_day, e_day)

                note = f"{prefix}-第{idx}次"
                finalize_range(s_day, e_day, note, adjusted)

        elif freq >= 4:
            count = freq
            for idx in range(1, 5):
                if count <= 0: break
                s_day = (idx-1)*7 + 1
                e_day = min(s_day + 6, self.days_in_month)
                s_day, e_day, adjusted = self._adjust_range_for_holiday(s_day, e_day)
                
                note = f"{prefix}-第{idx}次"
                finalize_range(s_day, e_day, note, adjusted, allow_window_shift=False)
                count -= 1

    def _find_next_fixed_day(self, start_day, item):
        """从 start_day 附近开始寻找该服务人员还能承接的服务日期。"""
        search_order = self._build_nearby_day_order(start_day)
        preferred_days = self._get_preferred_days_for_item(item, anchor_day=start_day)
        search_order = self._merge_preferred_days(search_order, preferred_days)
        search_order, _ = self._filter_days_by_order_capacity(search_order, item)
        search_order = self._sort_days_by_smoothing(search_order, item, start_day)
        for day in search_order:
            if self._is_holiday(day):
                continue
            return day
        return None

    def _get_special_requirement_col(self, df):
        special_col = self.cfg.get("SPECIAL_REQUIREMENT_COL", "特殊要求")
        legacy_col = self.cfg.get("LEGACY_SPECIAL_REQUIREMENT_COL", "指定日期")
        if special_col in df.columns:
            return special_col
        if legacy_col in df.columns:
            return legacy_col
        return None

    def run(self, df):
        required_cols = [
            self.cfg['LAST_MONTH_COL'],
            self.cfg['FREQ_COL'],
            self.cfg['SERVICE_PERSON_COL'],
            self.cfg['LAT_COL'],
            self.cfg['LNG_COL'],
            '品牌',
            '行政区划',
        ]
        missing = [col for col in required_cols if col not in df.columns]
        special_requirement_col = self._get_special_requirement_col(df)
        if special_requirement_col is None:
            missing.append(
                f"{self.cfg.get('SPECIAL_REQUIREMENT_COL', '特殊要求')}（旧表可用{self.cfg.get('LEGACY_SPECIAL_REQUIREMENT_COL', '指定日期')}）"
            )
        if missing:
            raise ValueError(f"❌ Excel 中找不到这些列: {missing}。\n请检查 CONFIG 配置中的列名是否与 Excel 表头一致。")

        queues = {'fixed': [], 'brand_specific': [], 'brand_range': [], 'remote': [], 'normal': [], 'quarterly': []}
        for idx, row in df.iterrows():
            item = row.to_dict()
            item['last_date_obj'] = self._parse_date_obj(row[self.cfg['LAST_MONTH_COL']])
            
            if item['last_date_obj'] and item['last_date_obj'].year == self.cfg["YEAR"]:
                if item['last_date_obj'].month > self.cfg["MONTH"]:
                    item['last_date_obj'] = item['last_date_obj'].replace(year=self.cfg["YEAR"] - 1)

            freq_num = self._clean_parse_freq(row[self.cfg['FREQ_COL']])
            item['clean_freq'] = freq_num 
            item['specified_date_rule'] = self._parse_specified_date_rule(row[special_requirement_col])

            specified_mode = item['specified_date_rule'].get('mode')
            is_brand_range = row['品牌'] in self.cfg.get("SPECIFIC_RANGE_BRANDS", [])
            if specified_mode not in ('none', 'unrecognized'):
                if is_brand_range and specified_mode in ('date_range', 'candidate_dates'):
                    queues['brand_range'].append(item)
                else:
                    queues['fixed'].append(item)
                continue

            if specified_mode == 'unrecognized':
                item['specified_date_warning'] = item['specified_date_rule'].get('warning', '特殊要求无法识别')

            if freq_num < 0.1:
                continue 

            # [新增] 指定品牌3天范围逻辑
            if is_brand_range:
                queues['brand_range'].append(item)

            # [修正 2] 品牌转为配置化判定（原有单日逻辑）
            elif row['品牌'] in self.cfg.get("SPECIFIC_DATE_BRANDS", []):
                queues['brand_specific'].append(item)
            
            elif row['行政区划'] in self.cfg["REMOTE_CITIES"] and freq_num >= 0.9:
                queues['remote'].append(item)
            else:
                if abs(freq_num - 0.3) < 0.01:
                    if self._should_schedule_quarterly(item):
                        queues['quarterly'].append(item)
                else:
                    queues['normal'].append(item)

        # 1. 特殊要求
        for item in queues['fixed']:
            resolved_days = self._resolve_specified_rule_days(item)
            if not resolved_days:
                item['specified_date_warning'] = item.get('specified_date_warning', '特殊要求无法识别')
                continue
            for start_day, end_day, anchor_day, used_relaxed, note_suffix in resolved_days:
                note = self._append_remote_tag("特殊要求", item)
                if note_suffix:
                    note += note_suffix
                if self._is_holiday(anchor_day):
                    note += "[警告:假期冲撞]"
                if not self._check_person_order_constraint(anchor_day, item, allow_relaxed=False):
                    if used_relaxed or self._check_person_order_constraint(anchor_day, item, allow_relaxed=True):
                        note += "[20日前放宽3单]"
                    else:
                        note += "[警告:人员日工单超限]"
                self._assign(start_day, end_day, item, note, is_fixed=True, fixed_day=anchor_day)

        # 2. 配置品牌的单日锁定逻辑
        for item in queues['brand_specific']:
            last_date = item['last_date_obj']
            anchor = self._get_brand_anchor_day(last_date)
            best = self._find_best_slot_soft(anchor, True, False, item=item)
            note = self._append_remote_tag("品牌单日", item)
            if not self._check_person_order_constraint(best, item, allow_relaxed=False):
                if self._check_person_order_constraint(best, item, allow_relaxed=True):
                    note += "[20日前放宽3单]"
                else:
                    note += "[警告:人员日工单超限]"
            self._assign(best, best, item, note, is_fixed=True)

        # 3. 配置品牌的3天范围逻辑
        # 规则：以窗口“最后一天(end_day)”作为服务锚点日期。
        # 若该服务人员当天工单已满额，则将 end_day 顺延到下一个可用日期，并整体平移窗口。
        # 为了“同一行政区划门店能一天多干一些”，优先按行政区划分组后再处理。
        brand_range_items = list(queues['brand_range'])
        brand_range_items.sort(
            key=lambda it: (str(it.get('行政区划', '')), self._get_brand_anchor_day(it.get('last_date_obj')))
        )
        for item in brand_range_items:
            last_date = item['last_date_obj']
            base_anchor = self._get_brand_anchor_day(last_date)
            # 按频次排班；异常值兜底为至少 1 次
            occurrences = max(1, int(round(item.get('clean_freq', 1))))
            min_gap_days = self._get_min_gap_days_for_frequency(occurrences)
            specified_allowed_end_days, specified_note = self._get_specified_brand_range_limit(item)
            target_weeks = []
            if occurrences == 2:
                target_weeks = self._get_alternating_weeks_from_last_date(last_date)
            elif occurrences == 4:
                target_weeks = [1, 2, 3, 4]

            # 非 2/4 次时，仍使用锚点推进避免全部挤在同一时段
            step_days = max(7, self.days_in_month // max(1, occurrences))
            rolling_anchor = base_anchor

            for occ_idx in range(1, occurrences + 1):
                allowed_end_days = None
                if occ_idx <= len(target_weeks):
                    week_no = target_weeks[occ_idx - 1]
                    week_start = (week_no - 1) * 7 + 1
                    week_end = min(week_start + 6, self.days_in_month)
                    allowed_end_days = list(range(week_start, week_end + 1))
                    anchor = min(max(week_start, base_anchor), week_end)
                else:
                    anchor = rolling_anchor
                if specified_allowed_end_days:
                    if allowed_end_days is None:
                        allowed_end_days = specified_allowed_end_days
                    else:
                        combined_allowed_days = [
                            day for day in allowed_end_days
                            if day in set(specified_allowed_end_days)
                        ]
                        allowed_end_days = combined_allowed_days or specified_allowed_end_days

                # 3天范围：优先选择假期天数更少的窗口；若无满足阈值则回退到最少假期窗口并告警
                start_day, end_day, service_day, holiday_days, used_relaxed, holiday_over_threshold = self._plan_brand_range_window(
                    anchor, item, allowed_end_days=allowed_end_days, min_gap_days=min_gap_days
                )
                max_holiday_days = int(self.cfg.get("BRAND_RANGE_MAX_HOLIDAY_DAYS", 1))

                note = self._append_remote_tag("3天范围门店", item)
                if specified_note:
                    note += specified_note
                if occurrences > 1:
                    note += f"-第{occ_idx}次"
                if occ_idx <= len(target_weeks):
                    note += f"-第{self._get_week_index(service_day)}周"
                if holiday_days >= 3:
                    note += "[警告:假期冲撞]"
                if holiday_over_threshold and holiday_days > max_holiday_days:
                    note += "[警告:假期天数超阈值]"
                if used_relaxed:
                    note += "[20日前放宽3单]"
                if not self._check_person_order_constraint(service_day, item, allow_relaxed=False):
                    if self._check_person_order_constraint(service_day, item, allow_relaxed=True):
                        note += "[20日前放宽3单]"
                    else:
                        note += "[警告:人员日工单超限]"

                self._assign(start_day, end_day, item, note, is_fixed=True, fixed_day=service_day)
                rolling_anchor = min(self.days_in_month, service_day + step_days)

        # 4. 偏远城市 (复用区间范围逻辑)
        for item in queues['remote']:
            self._assign_range(item, prefix="偏远门店", is_remote=True)

        # 5. 季度排班
        for item in queues['quarterly']:
            s_day, e_day = 1, self.days_in_month
            s_day, e_day, adjusted = self._adjust_range_for_holiday(s_day, e_day)
            note = "季度门店" + ("-假期避让" if adjusted else "")
            s_day, e_day, _service_day, aligned_adjusted, moved, _used_relaxed = self._align_range_window(
                s_day,
                e_day,
                item,
                enforce_weekly_capacity=True,
                allow_window_shift=False,
            )
            if aligned_adjusted and "-假期避让" not in note:
                note += "-假期避让"
            if moved and self._get_related_day_counter(item):
                note += "-近邻对齐"
            self._assign(s_day, e_day, item, note, remote_day=_service_day, load_mode="weekly")

        # 6. 常规排班
        for item in queues['normal']:
            self._assign_range(item, prefix="常规门店")

        return pd.DataFrame(self.final_schedule)
