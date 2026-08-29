"""B站专用公共库（纯标准库）：Cookie 持久化、wbi 签名、弹幕解析。

登录 Cookie 存 <技能根>/credentials/bilibili.json，含 SESSDATA 等凭证，
勿提交 git、勿外发、勿在对话中回显完整值。
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import zlib
from html import unescape
from pathlib import Path

from apilib import UA, http_json

ROOT = Path(__file__).resolve().parent.parent
CRED_DIR = ROOT / "credentials"
COOKIE_FILE = CRED_DIR / "bilibili.json"

# wbi 混淆表（来源 bilibili-API-collect 社区文档；官方换表时更新这里）
MIXIN_TAB = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27,
             43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48,
             7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54,
             21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]


def load_cookies() -> dict:
    if COOKIE_FILE.exists():
        data = json.loads(COOKIE_FILE.read_text("utf-8"))
        return {c["name"]: c["value"] for c in data.get("cookies", [])}
    return {}


def save_cookies(cookies: dict) -> None:
    CRED_DIR.mkdir(exist_ok=True)
    payload = {"saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "cookies": [{"name": k, "value": v, "domain": ".bilibili.com"}
                           for k, v in sorted(cookies.items())]}
    COOKIE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


def has_sessdata(cookies: dict) -> bool:
    return bool(cookies.get("SESSDATA"))


def fresh_identity() -> dict:
    """铸造全新匿名身份：buvid3/4（finger/spi）+ b_nut（主站下发）。

    风控挑战（data 只有 v_voucher）后换新身份重试用；成功则落盘。
    """
    fresh: dict = {}
    try:
        j = http_json("https://api.bilibili.com/x/frontend/finger/spi")
        fresh["buvid3"], fresh["buvid4"] = j["data"]["b_3"], j["data"]["b_4"]
    except Exception:  # noqa: BLE001
        pass
    try:
        req = urllib.request.Request("https://www.bilibili.com/",
                                     headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            for c in resp.headers.get_all("Set-Cookie") or []:
                kv = c.split(";", 1)[0]
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    fresh.setdefault(k.strip(), v.strip())
    except Exception:  # noqa: BLE001
        pass
    if fresh.get("buvid3"):
        save_cookies(fresh)
    return fresh


def ensure_buvid(cookies: dict) -> dict:
    """搜索接口需要 buvid3+b_nut，否则被风控软拦截（code 0 但结果为空）。"""
    if cookies.get("buvid3") and cookies.get("b_nut"):
        return cookies
    fresh = fresh_identity()
    for k, v in fresh.items():
        cookies.setdefault(k, v)
    return cookies


def is_risk_challenged(resp: dict) -> bool:
    """code 0 但 data 只剩 v_voucher = gaia 风控挑战，未返回真实结果。"""
    d = resp.get("data") or {}
    return bool(d.get("v_voucher")) and not d.get("result")


def get_wbi_keys(cookies: dict) -> tuple[str, str]:
    """未登录也能取 wbi_img key（nav 返回 code -101 但 data 里有）。"""
    j = http_json("https://api.bilibili.com/x/web-interface/nav", cookies=cookies)
    img = j["data"]["wbi_img"]
    return (img["img_url"].rsplit("/", 1)[1].split(".")[0],
            img["sub_url"].rsplit("/", 1)[1].split(".")[0])


def wbi_sign(params: dict, img_key: str, sub_key: str) -> dict:
    mixin = "".join((img_key + sub_key)[i] for i in MIXIN_TAB)[:32]
    p = dict(params)
    p["wts"] = int(time.time())
    p = {k: "".join(ch for ch in str(v) if ch not in "!'()*")
         for k, v in sorted(p.items())}
    query = urllib.parse.urlencode(p)
    p["w_rid"] = hashlib.md5((query + mixin).encode()).hexdigest()
    return p


_DANMAKU_RE = re.compile(r'<d p="([^"]+)"[^>]*>([^<]*)</d>')


def parse_danmaku(raw: bytes) -> list[dict]:
    """list.so 返回压缩的 XML。实测它会发"裸 deflate"（无 zlib 头）；
    兼容链：gzip → zlib → 裸 deflate → brotli（可选包）。"""
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    else:
        for wbits in (47, -15):  # 47=zlib 自动头；-15=裸 deflate（当前B站行为）
            try:
                raw = zlib.decompress(raw, wbits)
                break
            except zlib.error:
                continue

    def _match(text: str) -> list[tuple[str, str]]:
        return _DANMAKU_RE.findall(text)

    hits = _match(raw.decode("utf-8", "replace"))
    if not hits:  # 仍不是 XML → 大概率 brotli
        try:
            import brotli  # type: ignore
        except ImportError:
            raise RuntimeError(
                "弹幕数据无法解压（尝试过 gzip/zlib/裸deflate；疑似 brotli）。"
                "运行 `pip install brotli` 后重试，或跳过弹幕（字幕/评论不受影响）。") from None
        hits = _match(brotli.decompress(raw).decode("utf-8", "replace"))

    out: list[dict] = []
    for p, text in hits:
        fields = p.split(",")
        try:
            t = float(fields[0])
            mode = int(fields[1])
        except (ValueError, IndexError):
            continue
        if mode in (0, 1, 6):  # 普通/底部/滚动弹幕；过滤高级弹幕与代码弹幕
            txt = unescape(text).strip()
            if txt:
                out.append({"t": round(t, 1), "text": txt})
    out.sort(key=lambda d: d["t"])
    return out


def danmaku_bursts(items: list[dict], window: float = 30.0, top: int = 8) -> list[dict]:
    """30 秒窗口弹幕密度 = 观众爆点 ≈ 教学关键段。返回密度最高的片段。"""
    if not items:
        return []
    t0 = min(d["t"] for d in items)
    buckets: dict[int, list[str]] = {}
    for d in items:
        buckets.setdefault(int((d["t"] - t0) // window), []).append(d["text"])
    ranked = sorted(buckets.items(), key=lambda kv: -len(kv[1]))[:top]
    return [{"from_s": int(k * window), "to_s": int((k + 1) * window),
             "count": len(v), "sample": v[:3]}
            for k, v in sorted(ranked)]
