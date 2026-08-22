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
LIST_KEYS = ("REMOTE_CITIES", "SPECIFIC_DATE_BRANDS", "SPECIFIC_RANGE_BRANDS")
INTEGER_KEYS = (
    "SOFT_ANCHOR_TOLERANCE",
    "MAX_DAILY_ORDERS_PER_PERSON",
    "MAX_DAILY_ORDERS_PER_PERSON_RELAXED",
    "RELAXED_CAP_BEFORE_DAY",
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
    "REMOTE_MAX_SHIFT_DAYS",
    "BRAND_RANGE_MAX_HOLIDAY_DAYS",
    "REGULAR_FREQ1_WINDOW_DAYS",
    "QUARTERLY_INTERVAL_MONTHS",
)


def get_config_path() -> Path:
    configured = os.environ.get("SCHEDULER_CONFIG_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".zeosite" / "auto-scheduler" / "config.json"


def load_default_config() -> dict[str, Any]:
    return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


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
        raise ConfigError("每日严格上限必须至少为 1")
    if normalized["MAX_DAILY_ORDERS_PER_PERSON_RELAXED"] < normalized["MAX_DAILY_ORDERS_PER_PERSON"]:
        raise ConfigError("每日放宽上限不能小于严格上限")
    if not 1 <= normalized["RELAXED_CAP_BEFORE_DAY"] <= 31:
        raise ConfigError("放宽截止日期必须在 1 到 31 之间")
    if normalized["MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON"] < 1:
        raise ConfigError("每周容量必须至少为 1")
    if normalized["REGULAR_FREQ1_WINDOW_DAYS"] < 1 or normalized["REGULAR_FREQ1_WINDOW_DAYS"] > 31:
        raise ConfigError("单次服务窗口必须在 1 到 31 天之间")
    if normalized["QUARTERLY_INTERVAL_MONTHS"] < 1:
        raise ConfigError("季度间隔必须至少为 1 个月")

    overlap = set(normalized["SPECIFIC_DATE_BRANDS"]) & set(normalized["SPECIFIC_RANGE_BRANDS"])
    if overlap:
        raise ConfigError(f"品牌不能同时属于单日和三日范围规则：{', '.join(sorted(overlap))}")
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
    return validate_config(data)


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
