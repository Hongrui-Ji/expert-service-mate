from datetime import datetime

import pytest

from reporttowuye.monitoring_api import (
    MonitoringAPIError,
    parse_monitoring_row,
    select_latest_per_device,
)


def row_for(device_id: int, timestamp: int, recognition_info: str, point_name: str = "后厨"):
    return {
        "门店id": 944217,
        "门店名": "测试门店",
        "点位名称": point_name,
        "基本信息": f"<br>740-设备组 1<br>{device_id}-{point_name}<br>{recognition_info}",
        "image_url_oss": f"oss://chuxin-camera-image/2026/202605/{timestamp}.jpeg",
    }


def test_selects_latest_capture_for_each_device_even_when_rows_are_unsorted():
    rows = [
        row_for(6827, 1779747000, "识别类型：2"),
        row_for(6827, 1779749000, "识别类型：2"),
        row_for(6821, 1779748000, '{"count": 4}', "客区"),
    ]

    selected, dropped = select_latest_per_device(rows)

    assert dropped == 1
    assert [item.device_id for item in selected] == ["6827", "6821"]
    assert selected[0].oss_url.endswith("1779749000.jpeg")
    assert selected[0].recognition_type == 2
    assert selected[1].recognition_type == 3


def test_prefers_structured_fields_when_query_is_upgraded():
    item = parse_monitoring_row(
        {
            "store_id": "1",
            "store_name": "测试门店",
            "device_id": "20",
            "point_name": "库房",
            "recognition_type": 1,
            "captured_at": "2026-05-26T09:30:15+08:00",
            "oss_url": "oss://chuxin-camera-image/a/1779759015.jpeg",
        }
    )

    assert item.category == "mouse"
    assert item.captured_at == datetime(2026, 5, 26, 9, 30, 15)
    assert "bucket_name=chuxin-camera-image" in item.resolver_url


def test_rejects_rows_without_a_terminal_identity():
    with pytest.raises(MonitoringAPIError, match="终端ID"):
        parse_monitoring_row(
            {
                "门店id": 1,
                "门店名": "测试门店",
                "点位名称": "后厨",
                "基本信息": "识别类型：1",
                "image_url_oss": "oss://bucket/a/1779749000.jpeg",
            }
        )
