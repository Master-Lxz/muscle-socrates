"""抖音 cookie 工具：跨 agent 通用的凭证规范与格式互转（纯标准库）。

规范文件: credentials/douyin_cookies.json
  {"updated": "2026-08-29T12:00:00",
   "cookies": [{"name": "sessionid_ss", "value": "...", "domain": ".douyin.com",
                "path": "/", "expires": 1790000000.0}]}

子命令:
  check                       校验登录态（sessionid/sessionid_ss 存在且未过期，ttwid 存在）
  init                        生成空模板
  to-playwright <out.json>    转 Playwright storage_state（Playwright 系 agent 直接用）
  from-playwright <in.json>   从 Playwright storage_state 导入
  from-netscape <in.txt>      从 Netscape cookies.txt 导入（浏览器插件导出格式）

登录流程（任何浏览器工具均可）见 references/douyin.md。凭证勿提交 git、勿外发。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import apilib  # noqa: E402

CRED = pathlib.Path(__file__).resolve().parent.parent / "credentials" / "douyin_cookies.json"


def load() -> dict | None:
    if not CRED.exists():
        return None
    return json.loads(CRED.read_text("utf-8"))


def save(cookies: list[dict]) -> None:
    CRED.parent.mkdir(exist_ok=True)
    CRED.write_text(json.dumps(
        {"updated": time.strftime("%Y-%m-%dT%H:%M:%S"), "cookies": cookies},
        ensure_ascii=False, indent=2), "utf-8")


def cmd_check() -> dict:
    data = load()
    if not data:
        return {"valid": False, "reason": f"凭证文件不存在: {CRED} —— 先完成一次性扫码登录（见 references/douyin.md）"}
    by = {c["name"]: c for c in data.get("cookies", [])}
    sid = by.get("sessionid_ss") or by.get("sessionid")
    if not sid:
        return {"valid": False, "reason": "缺 sessionid/sessionid_ss —— 未登录或登录态丢失，请重新扫码"}
    exp = sid.get("expires") or 0
    if exp and exp < time.time():
        return {"valid": False, "reason": "sessionid 已过期，请重新扫码"}
    if not by.get("ttwid"):
        return {"valid": False, "reason": "缺 ttwid —— 请从登录用的浏览器重新完整导出（含 ttwid）"}
    return {"valid": True, "cookies": len(by), "updated": data.get("updated"),
            "note": "登录态有效；过期通常在数周后，check 失败就重新扫码"}


def cmd_to_playwright(out: str) -> str:
    data = load()
    if not data:
        raise SystemExit(f"凭证文件不存在: {CRED}")
    pw = {"cookies": [{"name": c["name"], "value": c["value"],
                       "domain": c.get("domain", ".douyin.com"),
                       "path": c.get("path", "/"),
                       "expires": c.get("expires", -1),
                       "httpOnly": False, "secure": True, "sameSite": "Lax"}
                      for c in data["cookies"]],
          "origins": []}
    pathlib.Path(out).write_text(json.dumps(pw, ensure_ascii=False, indent=2), "utf-8")
    return out


def _keep(c_domain: str) -> bool:
    return "douyin.com" in c_domain


def cmd_from_playwright(src: str) -> dict:
    pw = json.loads(pathlib.Path(src).read_text("utf-8"))
    kept = [{"name": c["name"], "value": c["value"], "domain": c.get("domain", ".douyin.com"),
             "path": c.get("path", "/"), "expires": c.get("expires", -1)}
            for c in pw.get("cookies", []) if _keep(c.get("domain", ""))]
    save(kept)
    return {"imported": len(kept),
            "skipped_other_domains": len(pw.get("cookies", [])) - len(kept)}


def cmd_from_netscape(src: str) -> dict:
    """只收 douyin.com 域：整 profile 导出的 cookies.txt 里会有全浏览器
    （Google/银行/邮箱…）的 cookie，混进这个"抖音专用、不外发"的凭证文件是事故。"""
    cookies: list[dict] = []
    skipped = 0
    for line in pathlib.Path(src).read_text("utf-8", "replace").splitlines():
        if not line.strip() or line.startswith("# "):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            if not _keep(parts[0]):
                skipped += 1
                continue
            cookies.append({"domain": parts[0], "path": parts[2], "name": parts[5],
                            "value": parts[6], "expires": float(parts[4] or 0)})
    save(cookies)
    return {"imported": len(cookies), "skipped_other_domains": skipped}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("init")
    p = sub.add_parser("to-playwright"); p.add_argument("out")
    p = sub.add_parser("from-playwright"); p.add_argument("src")
    p = sub.add_parser("from-netscape"); p.add_argument("src")
    a = ap.parse_args(argv)

    apilib.stdout_utf8()
    if a.cmd == "check":
        print(json.dumps(cmd_check(), ensure_ascii=False))
        return 0 if cmd_check()["valid"] else 2
    if a.cmd == "init":
        save([])
        print(f"已生成空模板: {CRED}")
        return 0
    if a.cmd == "to-playwright":
        print(json.dumps({"code": 0, "written": cmd_to_playwright(a.out)}, ensure_ascii=False))
        return 0
    if a.cmd == "from-playwright":
        r = cmd_from_playwright(a.src)
    elif a.cmd == "from-netscape":
        r = cmd_from_netscape(a.src)
    else:
        return 1
    print(json.dumps({"code": 0, "imported_from": a.src, **r}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
