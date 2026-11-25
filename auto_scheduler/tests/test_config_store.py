import json

import pytest

from auto_scheduler.config_store import (
    ConfigError,
    load_config,
    load_default_config,
    save_config,
)


def test_config_is_saved_and_reloaded_atomically(tmp_path):
    path = tmp_path / "config.json"
    config = load_default_config()
    config["REMOTE_CITIES"].append("测试区")

    saved = save_config(config, path=path)

    assert path.exists()
    assert load_config(path=path) == saved
    assert json.loads(path.read_text(encoding="utf-8"))["REMOTE_CITIES"][-1] == "测试区"
    assert not list(tmp_path.glob("*.tmp"))


def test_legacy_capacity_keys_are_ignored_on_load(tmp_path):
    """升级后旧配置里残留的“每日放宽上限”等键，不应让整份配置被判为非法。"""
    path = tmp_path / "config.json"
    legacy = load_default_config()
    legacy["MAX_DAILY_ORDERS_PER_PERSON_RELAXED"] = 3
    legacy["RELAXED_CAP_BEFORE_DAY"] = 20
    path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

    loaded = load_config(path=path)

    assert "MAX_DAILY_ORDERS_PER_PERSON_RELAXED" not in loaded
    assert "RELAXED_CAP_BEFORE_DAY" not in loaded
    assert loaded["MAX_DAILY_ORDERS_PER_PERSON"] == 4
    assert loaded["MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON"] == 25


def test_daily_limit_must_be_positive(tmp_path):
    config = load_default_config()
    config["MAX_DAILY_ORDERS_PER_PERSON"] = 0

    with pytest.raises(ConfigError, match="每日工单上限"):
        save_config(config, path=tmp_path / "config.json")


def test_old_default_capacity_values_are_migrated(tmp_path):
    """服务器上遗留的旧默认值（日 2 / 周 6）应自动迁移到新默认值（日 4 / 周 25）。"""
    path = tmp_path / "config.json"
    legacy = load_default_config()
    legacy["MAX_DAILY_ORDERS_PER_PERSON"] = 2
    legacy["MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON"] = 6
    legacy["NEARBY_ALIGN_RADIUS_METERS"] = 300
    path.write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

    loaded = load_config(path=path)

    assert loaded["MAX_DAILY_ORDERS_PER_PERSON"] == 4
    assert loaded["MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON"] == 25
    assert loaded["NEARBY_ALIGN_RADIUS_METERS"] == 150


def test_default_nearby_radius_is_150_meters():
    config = load_default_config()

    assert config["NEARBY_ALIGN_RADIUS_METERS"] == 150


def test_customised_capacity_values_are_kept(tmp_path):
    """业务手动改过的容量数值不应被默认值迁移覆盖。"""
    path = tmp_path / "config.json"
    custom = load_default_config()
    custom["MAX_DAILY_ORDERS_PER_PERSON"] = 3
    custom["MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON"] = 12
    path.write_text(json.dumps(custom, ensure_ascii=False), encoding="utf-8")

    loaded = load_config(path=path)

    assert loaded["MAX_DAILY_ORDERS_PER_PERSON"] == 3
    assert loaded["MAX_WEEKLY_ORDERS_NORMAL_QUARTERLY_PER_PERSON"] == 12


def test_legacy_fixed_window_end_uses_the_new_interval_limit(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"BRAND_RANGE_END_OFFSET_DAYS": 30}), encoding="utf-8")

    assert load_config(path=path)["BRAND_RANGE_MAX_INTERVAL_DAYS"] == 35


def test_three_day_interval_has_room_for_a_complete_window(tmp_path):
    config = load_default_config()
    config["BRAND_RANGE_MIN_INTERVAL_DAYS"] = 33
    config["BRAND_RANGE_MAX_INTERVAL_DAYS"] = 34

    with pytest.raises(ConfigError, match="至少要相差 2 天"):
        save_config(config, path=tmp_path / "config.json")


def test_brand_rule_lists_must_not_overlap(tmp_path):
    config = load_default_config()
    config["SPECIFIC_DATE_BRANDS"] = ["重复品牌"]
    config["SPECIFIC_RANGE_BRANDS"] = ["重复品牌"]

    with pytest.raises(ConfigError, match="不能同时属于"):
        save_config(config, path=tmp_path / "config.json")
