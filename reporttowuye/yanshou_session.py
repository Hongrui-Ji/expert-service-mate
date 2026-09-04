from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlparse


DEFAULT_BASE_URL = "https://yanshou1.honganhome.com"
DEFAULT_STATE_PATH = str(
    Path.home() / ".local" / "share" / "zeosite" / "terminal-report" / "yanshou-storage-state.json"
)
ALLOWED_RESOLVER_HOSTS = {"yanshou1.honganhome.com", "oss.honganhome.com"}


class YanshouError(RuntimeError):
    pass


class YanshouAuthRequired(YanshouError):
    pass


class YanshouBrowserMissing(YanshouError):
    pass


def _playwright():
    try:
        from playwright.sync_api import Error, TimeoutError, sync_playwright
    except ImportError as exc:
        raise YanshouBrowserMissing("服务器尚未安装扫码登录组件") from exc
    return sync_playwright, Error, TimeoutError


class YanshouSession:
    def __init__(self, state_path: str | os.PathLike[str] | None = None, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("YANSHOU_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        configured_path = state_path or os.environ.get("YANSHOU_STATE_PATH") or DEFAULT_STATE_PATH
        self.state_path = Path(configured_path).expanduser()
        self.login_url = f"{self.base_url}/login"
        self.auth_check_url = f"{self.base_url}/api/iam/role/get/me"

    def _ensure_state_dir(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.state_path.parent.chmod(0o700)
        except PermissionError:
            pass

    def _atomic_save_state(self, context) -> None:
        self._ensure_state_dir()
        fd, tmp_name = tempfile.mkstemp(prefix="yanshou-state-", suffix=".json", dir=self.state_path.parent)
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            context.storage_state(path=str(tmp_path))
            tmp_path.chmod(0o600)
            os.replace(tmp_path, self.state_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _response_is_authenticated(response) -> bool:
        if not response.ok:
            return False
        try:
            data = response.json()
        except Exception:
            return False
        return bool(data.get("success"))

    def has_saved_state(self) -> bool:
        return self.state_path.is_file() and self.state_path.stat().st_size > 0

    def check_authenticated(self) -> bool:
        if not self.has_saved_state():
            return False
        sync_playwright, _, _ = _playwright()
        try:
            with sync_playwright() as playwright:
                request = playwright.request.new_context(storage_state=str(self.state_path))
                try:
                    response = request.get(self.auth_check_url, timeout=15_000)
                    authenticated = self._response_is_authenticated(response)
                    if authenticated:
                        self._atomic_save_state(request)
                    return authenticated
                finally:
                    request.dispose()
        except Exception:
            return False

    def login_with_qr(
        self,
        on_qr: Callable[[bytes], None],
        on_status: Callable[[str], None] | None = None,
        timeout_seconds: int = 180,
    ) -> None:
        sync_playwright, playwright_error, playwright_timeout = _playwright()
        status = on_status or (lambda _: None)

        try:
            with sync_playwright() as playwright:
                try:
                    browser = playwright.chromium.launch(headless=True)
                except playwright_error as exc:
                    raise YanshouBrowserMissing(
                        "服务器缺少 Chromium，请执行 python -m playwright install chromium"
                    ) from exc

                context = browser.new_context(viewport={"width": 520, "height": 620})
                page = context.new_page()
                try:
                    status("正在加载钉钉二维码…")
                    page.goto(self.login_url, wait_until="domcontentloaded", timeout=30_000)
                    qr = page.locator("#SweepLogin")
                    qr.wait_for(state="visible", timeout=30_000)
                    # 钉钉二维码位于跨域 iframe 中，容器会先于二维码图像出现。
                    page.wait_for_timeout(1_500)
                    last_hash = ""
                    deadline = time.monotonic() + timeout_seconds

                    while time.monotonic() < deadline:
                        response = context.request.get(self.auth_check_url, timeout=10_000)
                        if self._response_is_authenticated(response):
                            self._atomic_save_state(context)
                            status("扫码成功，验收登录态已保存")
                            return

                        try:
                            image = qr.screenshot(type="png")
                            digest = hashlib.sha256(image).hexdigest()
                            if digest != last_hash:
                                on_qr(image)
                                last_hash = digest
                        except (playwright_timeout, playwright_error):
                            pass

                        status("请使用钉钉扫码并在手机上确认")
                        page.wait_for_timeout(1_500)

                    raise YanshouError("二维码登录等待超时，请重新生成二维码")
                finally:
                    context.close()
                    browser.close()
        except YanshouError:
            raise
        except Exception as exc:
            raise YanshouError(f"验收系统登录失败：{exc}") from exc

    @staticmethod
    def _validate_resolver_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_RESOLVER_HOSTS:
            raise YanshouError("图片地址不属于允许的验收系统域名")

    def download_images(self, resolver_urls: Iterable[str], max_bytes: int = 15 * 1024 * 1024) -> list[bytes]:
        if not self.has_saved_state():
            raise YanshouAuthRequired("请先使用钉钉扫码登录验收系统")

        urls = list(resolver_urls)
        for url in urls:
            self._validate_resolver_url(url)

        sync_playwright, _, _ = _playwright()
        with sync_playwright() as playwright:
            request = playwright.request.new_context(storage_state=str(self.state_path))
            try:
                auth_response = request.get(self.auth_check_url, timeout=15_000)
                if not self._response_is_authenticated(auth_response):
                    raise YanshouAuthRequired("验收系统登录已过期，请重新扫码")

                contents: list[bytes] = []
                for url in urls:
                    response = request.get(url, timeout=30_000)
                    content_type = (response.headers.get("content-type") or "").lower()
                    body = response.body()

                    if "application/json" in content_type:
                        try:
                            payload = json.loads(body.decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            payload = {}
                        error = payload.get("error") or {}
                        if error.get("code") == "AuthFailure":
                            raise YanshouAuthRequired("验收系统登录已过期，请重新扫码")
                        raise YanshouError(error.get("message") or "验收系统没有返回图片")

                    if not response.ok:
                        raise YanshouError(f"图片下载失败（HTTP {response.status}）")
                    if not body:
                        raise YanshouError("验收系统返回了空图片")
                    if len(body) > max_bytes:
                        raise YanshouError("单张图片超过 15 MB，已停止下载")
                    contents.append(body)

                self._atomic_save_state(request)
                return contents
            finally:
                request.dispose()
