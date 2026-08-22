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


def test_invalid_capacity_is_rejected(tmp_path):
    config = load_default_config()
    config["MAX_DAILY_ORDERS_PER_PERSON"] = 4
    config["MAX_DAILY_ORDERS_PER_PERSON_RELAXED"] = 3

    with pytest.raises(ConfigError, match="放宽上限"):
        save_config(config, path=tmp_path / "config.json")


def test_brand_rule_lists_must_not_overlap(tmp_path):
    config = load_default_config()
    config["SPECIFIC_DATE_BRANDS"] = ["重复品牌"]
    config["SPECIFIC_RANGE_BRANDS"] = ["重复品牌"]

    with pytest.raises(ConfigError, match="不能同时属于"):
        save_config(config, path=tmp_path / "config.json")
