from __future__ import annotations

import copy
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


DEFAULT_CONFIG_PATH = Path(__file__).with_name("default_config.json")

# 2026-09 参数调整：把仍停留在“旧默认值”的容量配置迁移到新默认值。
# 只有值恰好等于旧默认值时才迁移，业务手动改过的数值保持不动。
LEGACY_DEFAULT_MIGRATION: dict[str, dict[int, int]] = {
    "MAX_DAILY_ORDERS_PER_PERSON": {2: 4},
    "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON": {6: 25},
    "NEARBY_ALIGN_RADIUS_METERS": {300: 150},
}

LIST_KEYS = (
    "REMOTE_CITIES",
    "SPECIFIC_DATE_BRANDS",
    "SPECIFIC_RANGE_BRANDS",
    "DORM_KEYWORDS",
    "BRAND_RANGE_END_ANCHOR_BRANDS",
)
INTEGER_KEYS = (
    "MAX_DAILY_ORDERS_PER_PERSON",
    "MAX_MONTHLY_WORKDAYS_PER_PERSON",
    "MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON",
    "NEARBY_ALIGN_RADIUS_METERS",
    "SMOOTHING_ANCHOR_WEIGHT",
    "SMOOTHING_DAY_LOAD_WEIGHT",
    "SMOOTHING_NEIGHBOR_LOAD_WEIGHT",
    "SMOOTHING_NEARBY_ALIGN_BONUS",
    "REMOTE_DAILY_PAIR_TARGET",
    "REMOTE_MIN_GAP_DAYS_FREQ2",
    "REMOTE_MIN_GAP_DAYS_FREQ3PLUS",
    "REGULAR_MIN_GAP_DAYS_FREQ2",
    "REGULAR_MIN_GAP_DAYS_FREQ3",
    "REGULAR_MIN_GAP_DAYS_FREQ4PLUS",
    "BRAND_RANGE_MAX_HOLIDAY_DAYS",
    "BRAND_RANGE_END_OFFSET_DAYS",
    "BRAND_RANGE_MIN_INTERVAL_DAYS",
    "REGULAR_FREQ1_WINDOW_DAYS",
    "REGULAR_FREQ1_ANCHOR_DAYS",
    "QUARTERLY_INTERVAL_MONTHS",
)


def get_config_path() -> Path:
    configured = os.environ.get("SCHEDULER_CONFIG_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".zeosite" / "auto-scheduler" / "config.json"


def load_default_config() -> dict[str, Any]:
    return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


def _migrate_legacy_defaults(config: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(config)
    for key, mapping in LEGACY_DEFAULT_MIGRATION.items():
        if key not in migrated:
            continue
        try:
            current = int(migrated[key])
        except (TypeError, ValueError):
            continue
        if current in mapping:
            migrated[key] = mapping[current]
    return migrated


def _normalize_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ConfigError(f"{label} 必须是列表")
    seen: set[str] = set()
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    defaults = load_default_config()
    unknown = set(config) - set(defaults)
    if unknown:
        raise ConfigError(f"存在不支持的配置项：{', '.join(sorted(unknown))}")

    normalized = copy.deepcopy(defaults)
    normalized.update(copy.deepcopy(config))
    for key in LIST_KEYS:
        normalized[key] = _normalize_string_list(normalized[key], key)
    for key in INTEGER_KEYS:
        value = normalized[key]
        if isinstance(value, bool):
            raise ConfigError(f"{key} 必须是数字")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{key} 必须是整数") from exc
        if number < 0:
            raise ConfigError(f"{key} 不能小于 0")
        normalized[key] = number

    if normalized["MAX_DAILY_ORDERS_PER_PERSON"] < 1:
        raise ConfigError("每日工单上限必须至少为 1")
    if normalized["MAX_MONTHLY_WORKDAYS_PER_PERSON"] < 1:
        raise ConfigError("每月工作日上限必须至少为 1")
    if normalized["MAX_MONTHLY_WORKDAYS_PER_PERSON"] > 31:
        raise ConfigError("每月工作日上限不能超过 31 天")
    if normalized["MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON"] < 1:
        raise ConfigError("每周工单上限必须至少为 1")
    if normalized["REGULAR_FREQ1_WINDOW_DAYS"] < 1 or normalized["REGULAR_FREQ1_WINDOW_DAYS"] > 31:
        raise ConfigError("单次服务窗口必须在 1 到 31 天之间")
    if not 0 <= normalized["REGULAR_FREQ1_ANCHOR_DAYS"] <= 62:
        raise ConfigError("单次服务锚点天数必须在 0 到 62 天之间（0 表示沿用旧版「上月同日」）")
    if normalized["QUARTERLY_INTERVAL_MONTHS"] < 1:
        raise ConfigError("季度间隔必须至少为 1 个月")
    if not 1 <= normalized["BRAND_RANGE_END_OFFSET_DAYS"] <= 31:
        raise ConfigError("三日范围窗口截止锚定天数必须在 1 到 31 天之间")
    if not 0 <= normalized["BRAND_RANGE_MIN_INTERVAL_DAYS"] <= 31:
        raise ConfigError("三日范围最小间隔天数必须在 0 到 31 天之间")
    if normalized["BRAND_RANGE_MIN_INTERVAL_DAYS"] >= normalized["BRAND_RANGE_END_OFFSET_DAYS"]:
        raise ConfigError("三日范围最小间隔天数必须小于窗口截止锚定天数")

    overlap = set(normalized["SPECIFIC_DATE_BRANDS"]) & set(normalized["SPECIFIC_RANGE_BRANDS"])
    if overlap:
        raise ConfigError(f"品牌不能同时属于单日和三日范围规则：{', '.join(sorted(overlap))}")
    not_range_brand = set(normalized["BRAND_RANGE_END_ANCHOR_BRANDS"]) - set(normalized["SPECIFIC_RANGE_BRANDS"])
    if not_range_brand:
        raise ConfigError(f"窗口截止锚定品牌必须同时属于三日范围品牌：{', '.join(sorted(not_range_brand))}")
    return normalized


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or get_config_path()
    if not config_path.exists():
        return validate_config(load_default_config())
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"共享配置读取失败：{exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("共享配置必须是 JSON 对象")
    # 兼容历史配置：丢弃已下线的配置项（例如旧版的“日放宽上限”），
    # 避免升级后被 validate_config 判为非法配置而整份回退默认值。
    known_keys = set(load_default_config())
    filtered = {key: value for key, value in data.items() if key in known_keys}
    return validate_config(_migrate_legacy_defaults(filtered))


def save_config(config: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    normalized = validate_config(config)
    config_path = path or get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = config_path.with_suffix(config_path.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        temp_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=config_path.parent,
                prefix=f".{config_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_name = temp_file.name
                json.dump(normalized, temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_name, config_path)
            temp_name = None
        finally:
            if temp_name:
                Path(temp_name).unlink(missing_ok=True)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    return normalized


def restore_default_config(path: Path | None = None) -> dict[str, Any]:
    return save_config(load_default_config(), path=path)
