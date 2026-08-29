"""B站扫码登录：终端出二维码 → 用户B站APP扫码 → 自动保存 Cookie（含 SESSDATA）。

用法: python bilibili_login.py
二维码渲染优先用 qrcode 库，没有会自动 `pip install --user qrcode`（纯 Python）；
装不上时打印登录链接，可用任意二维码生成器转出再扫。
Cookie 存 credentials/bilibili.json —— 勿外传、勿提交 git。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import apilib  # noqa: E402
import bili_lib  # noqa: E402

GENERATE = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

WAIT_MSG = {86101: "等待扫码…", 86090: "已扫码，请在手机上确认…"}


def show_qr(url: str) -> None:
    try:
        import qrcode  # type: ignore
    except ImportError:
        print("未检测到 qrcode 库，自动安装（纯 Python 包，几秒）…")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--quiet",
                            "--disable-pip-version-check", "qrcode"], check=True)
            import qrcode  # type: ignore
        except Exception as e:  # noqa: BLE001
            print(f"自动安装失败（{e}）。请手动 `pip install qrcode` 后重跑，")
            print("或用任意二维码生成器把下面链接转成二维码再用B站APP扫：")
            print(url)
            sys.exit(1)
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.print_ascii(invert=True)


def poll_once(qrcode_key: str) -> dict | None:
    """单轮询循环直到成功/过期。返回 cookie dict；过期/超时返回 None。"""
    deadline = time.time() + 180
    while time.time() < deadline:
        req = urllib.request.Request(f"{POLL}?qrcode_key={qrcode_key}",
                                     headers={"User-Agent": apilib.UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            set_cookies = resp.headers.get_all("Set-Cookie") or []
        code = body["data"]["code"]
        if code == 0:
            cookies: dict = {}
            for c in set_cookies:
                kv = c.split(";", 1)[0]
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    cookies[k.strip()] = v.strip()
            if not cookies:  # 兜底：确认后的跳转 url 里也带 cookie
                for part in body["data"].get("url", "").split("?")[-1].split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        cookies[k] = v
            return cookies
        if code == 86038:
            return None  # 过期 → 外层重新生成
        print(f"\r{WAIT_MSG.get(code, f'状态码 {code}…')}   ", end="", flush=True)
        time.sleep(2)
    return None


def main() -> int:
    apilib.stdout_utf8()
    while True:
        j = apilib.http_json(GENERATE)
        qrcode_key, qr_url = j["data"]["qrcode_key"], j["data"]["url"]
        print("请用 B站APP 扫码登录（180 秒内有效）：")
        show_qr(qr_url)
        cookies = poll_once(qrcode_key)
        if cookies and cookies.get("SESSDATA"):
            break
        print("\n未完成/已过期，重新生成二维码…")
    cookies = bili_lib.ensure_buvid(cookies)
    bili_lib.save_cookies(cookies)
    saved = ", ".join(sorted(k for k in cookies
                             if k in ("SESSDATA", "bili_jct", "DedeUserID", "buvid3", "buvid4")))
    print(f"\n登录成功，已保存: {saved} → {bili_lib.COOKIE_FILE}")
    print("（凭证文件含 SESSDATA，勿提交 git、勿发给任何人）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
