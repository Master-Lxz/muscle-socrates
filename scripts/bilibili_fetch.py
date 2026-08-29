"""抓取B站视频的教学素材包：AI字幕（需登录）+ 弹幕爆点 + 高赞评论。

用法:
  python bilibili_fetch.py BV1xxx [BV2yyy ...] [--comments 15] [--bursts 8] [--out 素材包.json]
  （支持多个 BV；--out 时写 UTF-8 文件；stdout 输出 JSON 摘要）
字幕依赖 SESSDATA；未登录自动回退弹幕，并在 subtitle.note 里说明。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import apilib  # noqa: E402
import bili_lib  # noqa: E402

VIEW = "https://api.bilibili.com/x/web-interface/view"
PLAYER = "https://api.bilibili.com/x/player/wbi/v2"
DANMAKU = "https://api.bilibili.com/x/v1/dm/list.so"
REPLY = "https://api.bilibili.com/x/v2/reply"


def get_subtitles(bvid: str, cid: int, aid: int, cookies: dict) -> tuple[list, str]:
    if not bili_lib.has_sessdata(cookies):
        return [], "未登录（无 SESSDATA），AI字幕不可用，已回退弹幕时间轴；先跑 bilibili_login.py"
    try:
        img, sub = bili_lib.get_wbi_keys(cookies)
        params = bili_lib.wbi_sign({"bvid": bvid, "cid": cid, "aid": aid}, img, sub)
        j = apilib.http_json(PLAYER, params=params, cookies=cookies)
        subs = ((j.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        if not subs:
            return [], "该视频没有可用的AI字幕"
        # 优先中文轨；同语言里优先 ai_status==2（AI 识别完成，社区经验值）
        best = sorted(subs, key=lambda s: (
            0 if str(s.get("lan", "")).startswith("zh") else 1,
            0 if s.get("ai_status") == 2 else 1))[0]
        url = (best.get("subtitle_url") or "").replace("http://", "https://")
        body = apilib.http_json(url).get("body", [])
        segs = [{"t": round(b["from"], 1), "text": b["content"]} for b in body]
        return segs, f"字幕轨道: {best.get('lan_doc') or best.get('lan')} (ai_status={best.get('ai_status')})"
    except Exception as e:  # noqa: BLE001
        return [], f"字幕抓取失败: {e}"


def get_comments(aid: int, cookies: dict, want: int) -> list[dict]:
    out: list[dict] = []
    for pn in (1, 2):
        try:
            j = apilib.http_json(REPLY, params={"type": 1, "oid": aid, "pn": pn,
                                                "ps": 20, "sort": 1}, cookies=cookies)
        except Exception:  # noqa: BLE001
            break
        for r in (j.get("data") or {}).get("replies") or []:
            out.append({"user": (r.get("member") or {}).get("uname", ""),
                        "like": r.get("like") or 0,
                        "text": ((r.get("content") or {}).get("message") or "")[:300]})
        page = (j.get("data") or {}).get("page") or {}
        if len(out) >= want * 2 or page.get("count", 0) <= pn * 20:
            break
    return sorted(out, key=lambda x: -x["like"])[:want]


def fetch_one(raw_bvid: str, cookies: dict, a) -> dict | None:
    bvid = raw_bvid.strip("/").split("/")[-1]
    v = apilib.http_json(VIEW, params={"bvid": bvid}, cookies=cookies)
    if v.get("code") != 0:
        print(json.dumps({"code": v.get("code"), "message": v.get("message"),
                          "bvid": bvid}, ensure_ascii=False))
        return None
    d = v["data"]
    aid, cid = d["aid"], d["cid"]

    segs, note = get_subtitles(bvid, cid, aid, cookies)
    dm: list[dict] = []
    dm_note = ""
    try:
        dm = bili_lib.parse_danmaku(apilib.http_bytes(DANMAKU, params={"oid": cid},
                                                      cookies=cookies))
    except RuntimeError as e:
        dm_note = str(e)
    return {
        "video": {
            "bvid": bvid, "aid": aid, "cid": cid,
            "title": d.get("title"),
            "owner": (d.get("owner") or {}).get("name"),
            "owner_mid": (d.get("owner") or {}).get("mid"),
            "pubdate": d.get("pubdate"),
            "duration_s": d.get("duration"),
            "view": (d.get("stat") or {}).get("view"),
            "danmaku_count": (d.get("stat") or {}).get("danmaku"),
            "url": f"https://www.bilibili.com/video/{bvid}",
        },
        "subtitle": {"note": note, "segments": segs},
        "danmaku": {"note": dm_note, "fetched": len(dm),
                    "bursts_30s": bili_lib.danmaku_bursts(dm, top=a.bursts)},
        "comments": get_comments(aid, cookies, a.comments),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bvid", nargs="+", help="BV 号或完整视频链接（可多个）")
    ap.add_argument("--comments", type=int, default=15)
    ap.add_argument("--bursts", type=int, default=8)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    apilib.stdout_utf8()
    cookies = bili_lib.load_cookies()

    packs: list[dict] = []
    for raw in a.bvid:
        pack = fetch_one(raw, cookies, a)
        if pack is None:
            return 1
        packs.append(pack)

    result = packs[0] if len(packs) == 1 else {"videos": packs}
    if a.out:
        pathlib.Path(a.out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
        print(json.dumps({"code": 0, "written": a.out, "videos": len(packs),
                          "titles": [p["video"]["title"] for p in packs],
                          "danmaku_total": sum(p["danmaku"]["fetched"] for p in packs),
                          "comments_total": sum(len(p["comments"]) for p in packs)},
                         ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
