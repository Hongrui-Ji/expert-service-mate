from __future__ import annotations

import html
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Iterable
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import requests


DEFAULT_REDASH_URL = "https://redash.honganhome.com"
DEFAULT_QUERY_ID = 51060
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class MonitoringAPIError(RuntimeError):
    """The Redash query could not be executed or parsed."""


@dataclass(frozen=True)
class MonitoringImage:
    store_id: str
    store_name: str
    device_id: str
    point_name: str
    recognition_type: int
    captured_at: datetime | None
    resolver_url: str
    oss_url: str

    @property
    def category(self) -> str:
        return {1: "mouse", 2: "roach", 3: "fly"}.get(self.recognition_type, "unknown")

    @property
    def category_label(self) -> str:
        return {
            1: "智能粘鼠板",
            2: "智能蟑螂屋",
            3: "智能灭蝇灯",
        }.get(self.recognition_type, "未知终端")


def _first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _clean_basic_info(value: Any) -> list[str]:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _parse_device_id(row: dict[str, Any], info_lines: list[str]) -> str:
    direct = _first_value(row, "device_id", "终端ID", "终端id", "点位ID", "点位id")
    if direct is not None:
        return str(direct).replace(",", "").strip()

    # 51060 的“基本信息”依次为设备组、终端点位、识别信息。
    ids = []
    for line in info_lines:
        match = re.match(r"^(\d+)\s*-", line)
        if match:
            ids.append(match.group(1))
    if len(ids) >= 2:
        return ids[1]
    if ids:
        return ids[0]
    return ""


def _parse_recognition_type(row: dict[str, Any], info_lines: list[str]) -> int:
    direct = _first_value(row, "recognition_type", "识别类型", "终端类型", "设备类型")
    if direct is not None:
        value = str(direct).strip()
        label_map = {
            "智能粘鼠板": 1,
            "粘鼠板": 1,
            "智能蟑螂屋": 2,
            "蟑螂屋": 2,
            "智能灭蝇灯": 3,
            "灭蝇灯": 3,
        }
        if value in label_map:
            return label_map[value]
        match = re.search(r"[123]", value)
        if match:
            return int(match.group(0))

    info = "\n".join(info_lines)
    match = re.search(r"识别类型\s*[:：]\s*([123])", info)
    if match:
        return int(match.group(1))

    # 51060 对 recognition_type=3 直接输出飞虫识别 JSON，而不输出类型数字。
    if re.search(r'["\']?count["\']?\s*:', info, flags=re.IGNORECASE):
        return 3
    return 0


def _parse_datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif value:
        raw = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is not None:
        return dt.astimezone(SHANGHAI_TZ).replace(tzinfo=None)
    return dt


def _parse_capture_time(row: dict[str, Any], oss_url: str) -> datetime | None:
    direct = _first_value(
        row,
        "captured_at",
        "capture_time",
        "create_time",
        "拍摄时间",
        "采集时间",
        "创建时间",
    )
    parsed = _parse_datetime_value(direct)
    if parsed is not None:
        return parsed

    # 现有 OSS 文件名以 Unix 秒级时间戳开头，例如 1779747140_sr4.jpeg。
    filename = PurePosixPath(urlparse(oss_url).path).name
    match = re.match(r"^(\d{10})(?:_|\.)", filename)
    if not match:
        return None
    try:
        return (
            datetime.fromtimestamp(int(match.group(1)), tz=timezone.utc)
            .astimezone(SHANGHAI_TZ)
            .replace(tzinfo=None)
        )
    except (OverflowError, OSError, ValueError):
        return None


def _build_resolver_url(oss_url: str) -> str:
    if not oss_url.startswith("oss://"):
        return ""
    remainder = oss_url[6:]
    bucket, separator, object_name = remainder.partition("/")
    if not separator or not bucket or not object_name:
        return ""
    return (
        "https://yanshou1.honganhome.com/api/ticket/get/aly/oss/url.json"
        f"?bucket_name={quote(bucket, safe='')}&object_name={quote(object_name, safe='/')}"
    )


def parse_monitoring_row(row: dict[str, Any]) -> MonitoringImage:
    info_lines = _clean_basic_info(_first_value(row, "基本信息", "basic_info"))
    oss_url = str(_first_value(row, "image_url_oss", "oss_url") or "").strip()
    resolver_url = str(_first_value(row, "图片链接", "resolver_url", "image_url") or "").strip()
    if not resolver_url:
        resolver_url = _build_resolver_url(oss_url)

    point_name = str(_first_value(row, "点位名称", "point_name", "location") or "").strip()
    store_id = str(_first_value(row, "门店id", "门店ID", "store_id") or "").replace(",", "").strip()
    store_name = str(_first_value(row, "门店名", "门店名称", "store_name") or "").strip()
    device_id = _parse_device_id(row, info_lines)
    recognition_type = _parse_recognition_type(row, info_lines)

    missing = []
    if not store_id:
        missing.append("门店ID")
    if not point_name:
        missing.append("点位名称")
    if not device_id:
        missing.append("终端ID")
    if recognition_type not in (1, 2, 3):
        missing.append("终端类型")
    if not resolver_url:
        missing.append("图片地址")
    if missing:
        raise MonitoringAPIError(f"监测数据缺少字段：{', '.join(missing)}")

    return MonitoringImage(
        store_id=store_id,
        store_name=store_name,
        device_id=device_id,
        point_name=point_name,
        recognition_type=recognition_type,
        captured_at=_parse_capture_time(row, oss_url),
        resolver_url=resolver_url,
        oss_url=oss_url,
    )


def select_latest_per_device(rows: Iterable[dict[str, Any]]) -> tuple[list[MonitoringImage], int]:
    """Return one image per terminal, choosing its latest capture for the day."""
    latest: dict[str, tuple[int, MonitoringImage]] = {}
    parsed_count = 0

    for row_index, row in enumerate(rows):
        image = parse_monitoring_row(row)
        parsed_count += 1
        current = latest.get(image.device_id)
        if current is None:
            latest[image.device_id] = (row_index, image)
            continue

        first_index, current_image = current
        if image.captured_at and (
            current_image.captured_at is None or image.captured_at > current_image.captured_at
        ):
            latest[image.device_id] = (first_index, image)

    # 保留 SQL 首次出现的终端顺序，方便报告版式稳定。
    selected = [item[1] for item in sorted(latest.values(), key=lambda item: item[0])]
    return selected, parsed_count - len(selected)


class RedashMonitoringClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_REDASH_URL,
        query_id: int = DEFAULT_QUERY_ID,
        timeout_seconds: int = 60,
    ) -> None:
        if not api_key:
            raise MonitoringAPIError("未配置 Redash 用户 API 密钥")
        self.base_url = base_url.rstrip("/")
        self.query_id = int(query_id)
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Key {api_key}",
                "Content-Type": "application/json",
            }
        )

    def _get_result_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        query_result = payload.get("query_result")
        if query_result:
            return list((query_result.get("data") or {}).get("rows") or [])

        job = payload.get("job")
        if not job or not job.get("id"):
            raise MonitoringAPIError("Redash 未返回查询结果或任务编号")

        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            response = self.session.get(
                f"{self.base_url}/api/jobs/{job['id']}",
                timeout=(5, 20),
            )
            response.raise_for_status()
            job = response.json().get("job") or {}
            status = job.get("status")
            if status == 3:
                result_id = job.get("query_result_id")
                if not result_id:
                    raise MonitoringAPIError("Redash 查询成功但没有结果编号")
                result_response = self.session.get(
                    f"{self.base_url}/api/query_results/{result_id}",
                    timeout=(5, 30),
                )
                result_response.raise_for_status()
                result = result_response.json().get("query_result") or {}
                return list((result.get("data") or {}).get("rows") or [])
            if status in (4, 5):
                message = job.get("error") or "查询失败"
                raise MonitoringAPIError(f"Redash 查询失败：{message}")
            time.sleep(0.5)

        raise MonitoringAPIError("Redash 查询超时，请稍后重试")

    def fetch_latest_images(
        self,
        report_date: date | str,
        store_id: str | int,
        max_age_seconds: int = 300,
    ) -> tuple[list[MonitoringImage], int, int]:
        date_value = report_date.isoformat() if isinstance(report_date, date) else str(report_date)
        try:
            numeric_store_id = int(str(store_id).replace(",", "").strip())
        except ValueError as exc:
            raise MonitoringAPIError("门店 ID 必须是数字") from exc

        response = self.session.post(
            f"{self.base_url}/api/queries/{self.query_id}/results",
            json={
                "parameters": {"date": date_value, "门店ID": numeric_store_id},
                "max_age": max_age_seconds,
            },
            timeout=(5, 30),
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise MonitoringAPIError(f"Redash 接口请求失败（HTTP {response.status_code}）") from exc

        rows = self._get_result_rows(response.json())
        selected, duplicate_count = select_latest_per_device(rows)
        return selected, len(rows), duplicate_count


def client_from_environment() -> RedashMonitoringClient:
    # 参数化查询可能启动异步任务；Redash 查询级 Key 无权轮询该任务，必须使用用户 API Key。
    api_key = os.environ.get("REDASH_API_KEY") or ""
    return RedashMonitoringClient(
        api_key=api_key,
        base_url=os.environ.get("REDASH_BASE_URL", DEFAULT_REDASH_URL),
        query_id=int(os.environ.get("REDASH_QUERY_ID", str(DEFAULT_QUERY_ID))),
    )
