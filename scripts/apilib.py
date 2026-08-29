"""公共 HTTP 小库（纯标准库）：所有脚本共用。

- http_bytes / http_json：带 UA、gzip 解压、简单重试
- stdout_utf8()：Windows 控制台输出兜底，避免 GBK 编码崩溃
"""
from __future__ import annotations

import gzip
import io
import json
import sys
import time
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def http_bytes(url: str, params: dict | None = None, headers: dict | None = None,
               cookies: dict | None = None, method: str = "GET", data=None,
               timeout: int = 25, retries: int = 1) -> bytes:
    """GET/POST。params 自动 urlencode 追加；cookies 拼 Cookie 头；失败重试后抛最后一次异常。"""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if headers:
        h.update(headers)
    if cookies:
        h["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    body = data.encode("utf-8") if isinstance(data, str) else data
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=h, data=body, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
                return raw
        except Exception as e:  # noqa: BLE001 - 统一重试，最后抛出
            last_exc = e
            time.sleep(1.5 * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def http_json(url: str, **kw) -> dict:
    return json.loads(http_bytes(url, **kw).decode("utf-8", "replace"))


def stdout_utf8() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - 非 Windows 或已重配置时忽略
            pass
