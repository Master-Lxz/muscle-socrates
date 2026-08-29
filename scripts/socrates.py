"""肌格拉底统一命令行入口 —— 所有功能一行命令搞定（纯标准库）。

用法: python "<技能根>/scripts/socrates.py" <命令> [参数]

命令:
  status                              一键体检：登录态 / 依赖 / wiki 条目数 / 文献源连通
  paper "<英文检索式>" [--max 8]       三源文献检索（Europe PMC + OpenAlex + Crossref）
  paper --fulltext PMC123 [--out 文件]  Europe PMC OA 全文（深挖档）
  verify <DOI或PMID>...               引用硬校验（exit 2 = 有问题，必须中断）
  bili-login                          B站扫码登录（首次跑一次）
  bili-search <关键词> [--author 名] [--limit 20]
  bili-fetch <BV号...> [--out 素材包.json]   抓字幕/弹幕爆点/高赞评论（支持多个BV）
  douyin check|init|to-playwright OUT|from-playwright SRC|from-netscape SRC

各子功能也保留独立脚本（scripts/ 下同名 .py），但一律推荐走本入口。
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

apilib.stdout_utf8()

import bili_lib  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def cmd_status(_args) -> int:
    """一键体检：agent 接手任何健身问题前先跑这个。"""
    cookies = bili_lib.load_cookies()
    report: dict = {"python": sys.version.split()[0]}

    report["bilibili"] = {
        "logged_in": bili_lib.has_sessdata(cookies),
        "buvid": bool(cookies.get("buvid3")),
        "cookie_file": str(bili_lib.COOKIE_FILE),
    }

    import douyin_cookies
    report["douyin"] = douyin_cookies.cmd_check()

    deps = {}
    for m in ("qrcode", "brotli"):
        try:
            __import__(m)
            deps[m] = True
        except ImportError:
            deps[m] = False
    report["optional_deps"] = deps

    # wiki 条目数 + 90 天过期检查（条目 frontmatter 里的"更新日期"字段）
    import datetime
    entries, stale = [], []
    for p in (ROOT / "wiki").glob("*.md"):
        if p.name.startswith("_"):
            continue
        entries.append(p.stem)
        m = re.search(r"更新日期:\s*(\d{4}-\d{2}-\d{2})",
                      p.read_text("utf-8", "replace"))
        if m:
            age = (datetime.date.today()
                   - datetime.date.fromisoformat(m.group(1))).days
            if age > 90:
                stale.append({"entry": p.stem, "age_days": age})
    report["wiki"] = {"entries": sorted(entries), "stale_over_90d": stale,
                      "hint": "stale 条目回答前建议重跑管线更新"}

    try:
        t0 = time.time()
        j = apilib.http_json(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={"query": "exercise", "format": "json", "pageSize": 1},
            timeout=8, retries=0)
        report["europepmc"] = {"ok": "hitCount" in j or "resultList" in j,
                               "ms": int((time.time() - t0) * 1000)}
    except Exception as e:  # noqa: BLE001
        report["europepmc"] = {"ok": False, "error": str(e)[:120]}

    hints = []
    if not report["bilibili"]["logged_in"]:
        hints.append("B站未登录：跑 bili-login 扫码（AI字幕需要；搜索/弹幕/评论不受影响）")
    if not report["douyin"].get("valid"):
        hints.append("抖音未登录：见 references/douyin.md 一次性扫码导出 cookie")
    if not deps["qrcode"]:
        hints.append("未装 qrcode：bili-login 时会自动补装")
    report["hints"] = hints
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_paper(args) -> int:
    import search_papers
    if args.fulltext:
        return search_papers.fulltext(args.fulltext, args.out)
    if not args.query:
        print(json.dumps({"code": -1, "message": "需要检索式，或用 --fulltext PMCID"}))
        return 1
    sources = {"europepmc": search_papers.europepmc,
               "openalex": search_papers.openalex,
               "crossref": search_papers.crossref}
    if args.source != "all":
        sources = {args.source: sources[args.source]}
    results: dict = {}
    for name, fn in sources.items():
        try:
            results[name] = fn(args.query, args.max)
        except Exception as e:  # noqa: BLE001
            results[name] = [{"error": str(e)}]
    print(json.dumps({"query": args.query, "results": results}, ensure_ascii=False))
    return 0


def cmd_verify(args) -> int:
    import verify_citations
    results = [verify_citations.check(x) for x in args.ids]
    bad = [r for r in results if r["status"] != "verified"]
    print(json.dumps({"all_verified": not bad, "results": results}, ensure_ascii=False))
    return 2 if bad else 0


def cmd_bili_login(_args) -> int:
    import bilibili_login
    return bilibili_login.main()


def cmd_bili_search(args) -> int:
    import bilibili_search
    argv = [args.keyword]
    if args.author:
        argv += ["--author", args.author]
    argv += ["--limit", str(args.limit)]
    return bilibili_search.main(argv)


def cmd_bili_fetch(args) -> int:
    import bilibili_fetch
    argv = list(args.bvid) + ["--comments", str(args.comments),
                              "--bursts", str(args.bursts)]
    if args.out:
        argv += ["--out", args.out]
    return bilibili_fetch.main(argv)


def cmd_douyin(args) -> int:
    import douyin_cookies as dc
    cmd = args.douyin_cmd
    if cmd in ("to-playwright", "from-playwright", "from-netscape") and not args.path:
        print(json.dumps({"code": -1, "message": f"{cmd} 需要文件路径参数"}))
        return 1
    if cmd == "check":
        r = dc.cmd_check()
        print(json.dumps(r, ensure_ascii=False))
        return 0 if r["valid"] else 2
    if cmd == "init":
        dc.save([])
        print(f"已生成空模板: {dc.CRED}")
        return 0
    if cmd == "to-playwright":
        print(json.dumps({"code": 0, "written": dc.cmd_to_playwright(args.path)},
                         ensure_ascii=False))
        return 0
    if cmd == "from-playwright":
        r = dc.cmd_from_playwright(args.path)
    elif cmd == "from-netscape":
        r = dc.cmd_from_netscape(args.path)
    else:
        return 0
    print(json.dumps({"code": 0, "imported_from": args.path, **r}, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="socrates.py", description="肌格拉底 —— 循证健身技能统一命令行")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="一键体检（登录态/依赖/wiki/文献源）")

    p = sub.add_parser("paper", help="文献检索 / OA 全文")
    p.add_argument("query", nargs="?", help="英文检索式")
    p.add_argument("--max", type=int, default=8)
    p.add_argument("--source", default="all",
                   choices=["all", "europepmc", "openalex", "crossref"])
    p.add_argument("--fulltext", metavar="PMCID", help="改为抓取 OA 全文")
    p.add_argument("--out", default=None)

    p = sub.add_parser("verify", help="引用硬校验")
    p.add_argument("ids", nargs="+", help="DOI 或 PMID（可多个）")

    sub.add_parser("bili-login", help="B站扫码登录")

    p = sub.add_parser("bili-search", help="B站视频搜索")
    p.add_argument("keyword")
    p.add_argument("--author", default=None)
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("bili-fetch", help="抓取视频素材包（可多个BV）")
    p.add_argument("bvid", nargs="+")
    p.add_argument("--comments", type=int, default=15)
    p.add_argument("--bursts", type=int, default=8)
    p.add_argument("--out", default=None)

    p = sub.add_parser("douyin", help="抖音 cookie 管理")
    p.add_argument("douyin_cmd",
                   choices=["check", "init", "to-playwright",
                            "from-playwright", "from-netscape"])
    p.add_argument("path", nargs="?", default=None)

    args = ap.parse_args()
    handler = {
        "status": cmd_status, "paper": cmd_paper, "verify": cmd_verify,
        "bili-login": cmd_bili_login, "bili-search": cmd_bili_search,
        "bili-fetch": cmd_bili_fetch, "douyin": cmd_douyin,
    }[args.cmd]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
