"""B站视频搜索（wbi 签名 + buvid）。

用法:
  python bilibili_search.py "深蹲 教学" [--author 凯圣王] [--limit 20]
stdout 输出 JSON:
  {"code": 0, "query": "...", "count": n,
   "results": [{"bvid","aid","title","author","mid","play","danmaku","favorites",
                "pubdate","duration_s","desc","url"}]}
code -412 = 风控：先跑 bilibili_login.py 扫码，或降低频率重试。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import apilib  # noqa: E402
import bili_lib  # noqa: E402

API = "https://api.bilibili.com/x/web-interface/wbi/search/type"
CONFIG = pathlib.Path(__file__).resolve().parent.parent / "config" / "creators.json"


def load_whitelist() -> tuple[set, set]:
    """读 UP主白名单（config/creators.json），返回 (名字集合, B站uid集合)。

    配置缺失/损坏时静默降级为空集——搜索照常工作，只是没有置顶。
    """
    try:
        cfg = json.loads(CONFIG.read_text("utf-8"))
    except Exception:  # noqa: BLE001
        return set(), set()
    names, uids = set(), set()
    for p in cfg.get("preferred", []):
        if p.get("name"):
            names.add(str(p["name"]).lower())
        uid = (p.get("uid") or {}).get("bilibili")
        if isinstance(uid, int):
            uids.add(uid)
    return names, uids


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword", help="搜索关键词（中文即可）")
    ap.add_argument("--author", default=None, help="只保留 UP主名包含该子串的结果")
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args(argv)

    apilib.stdout_utf8()
    cookies = bili_lib.ensure_buvid(bili_lib.load_cookies())

    def do_search(ck: dict) -> dict:
        img, sub = bili_lib.get_wbi_keys(ck)
        params = bili_lib.wbi_sign(
            {"search_type": "video", "keyword": a.keyword, "page": 1}, img, sub)
        return apilib.http_json(
            API, params=params, cookies=ck,
            headers={"Referer": "https://search.bilibili.com/"})

    try:
        j = do_search(cookies)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"code": -1, "message": f"请求失败: {e}"}))
        return 1

    # 风控挑战：换全新匿名身份重试一次；仍不行就如实上报，让 agent 提示扫码
    if bili_lib.is_risk_challenged(j):
        time.sleep(5)
        cookies = bili_lib.fresh_identity()
        try:
            j = do_search(cookies)
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"code": -1, "message": f"重试请求失败: {e}"}))
            return 1

    if j.get("code") != 0:
        print(json.dumps({"code": j.get("code"), "message": j.get("message"),
                          "hint": "code=-412 通常是风控：先 python bilibili_login.py 扫码，或稍后重试"}))
        return 1
    if bili_lib.is_risk_challenged(j):
        print(json.dumps({
            "code": -412, "message": "搜索触发B站风控挑战（v_voucher），未登录匿名搜索不稳定",
            "hint": "首选：python bilibili_login.py 扫码登录后再搜（登录态稳定）；"
                    "或等待几分钟后降低频率重试。view/弹幕/评论接口不受影响，可先抓已知 BV 号。"}))
        return 1

    rows = (j.get("data") or {}).get("result") or []
    # "剥壳"降级检测：B站反爬有时返回只有标题、剥掉作者/mid 的行——白名单和重排都废掉。
    # 表现为全部行无 author/uname，处理：换新身份重试一次，拿不回就用残缺行如实输出。
    if rows and not any(r.get("author") or r.get("uname") for r in rows):
        time.sleep(5)
        cookies = bili_lib.fresh_identity()
        try:
            j2 = do_search(cookies)
            if j2.get("code") == 0 and not bili_lib.is_risk_challenged(j2):
                rows = (j2.get("data") or {}).get("result") or rows
        except Exception:  # noqa: BLE001 - 重试失败就用原始降级行
            pass

    names, wuids = load_whitelist()
    results = []
    for r in rows:
        if r.get("type") != "video":
            continue
        author = r.get("author") or r.get("uname") or ""
        mid = r.get("mid") or r.get("uid")
        pubdate = r.get("pubdate")
        results.append({
            "bvid": r.get("bvid"),
            "aid": r.get("aid"),
            "title": re.sub(r"<.*?>", "", r.get("title") or ""),
            "author": author,
            "mid": mid,
            "whitelist": author.lower() in names or mid in wuids,
            "play": r.get("play"),
            "danmaku": r.get("video_review"),
            "favorites": r.get("favorites"),
            "pubdate": time.strftime("%Y-%m-%d", time.localtime(pubdate)) if pubdate else None,
            "duration_s": r.get("duration"),
            "desc": (r.get("description") or "")[:120],
            "url": f"https://www.bilibili.com/video/{r.get('bvid')}",
        })

    if a.author:  # 定向检索：只保留 UP主名包含该子串的结果
        results = [r for r in results if a.author.lower() in r["author"].lower()]

    # 白名单置顶：稳定排序，两组内部保持B站原相关性顺序
    results.sort(key=lambda x: not x["whitelist"])
    results = results[:a.limit]

    print(json.dumps({"code": 0, "query": a.keyword,
                      "count": len(results),
                      "whitelist_count": sum(1 for r in results if r["whitelist"]),
                      "whitelist_ups": sorted({r["author"] for r in results if r["whitelist"]}),
                      "results": results},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
