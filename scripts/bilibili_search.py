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

    results = []
    for r in (j.get("data") or {}).get("result") or []:
        if r.get("type") != "video":
            continue
        author = r.get("author") or ""
        if a.author and a.author.lower() not in author.lower():
            continue
        pubdate = r.get("pubdate")
        results.append({
            "bvid": r.get("bvid"),
            "aid": r.get("aid"),
            "title": re.sub(r"<.*?>", "", r.get("title") or ""),
            "author": author,
            "mid": r.get("mid"),
            "play": r.get("play"),
            "danmaku": r.get("video_review"),
            "favorites": r.get("favorites"),
            "pubdate": time.strftime("%Y-%m-%d", time.localtime(pubdate)) if pubdate else None,
            "duration_s": r.get("duration"),
            "desc": (r.get("description") or "")[:120],
            "url": f"https://www.bilibili.com/video/{r.get('bvid')}",
        })
        if len(results) >= a.limit:
            break
    print(json.dumps({"code": 0, "query": a.keyword,
                      "count": len(results), "results": results},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
