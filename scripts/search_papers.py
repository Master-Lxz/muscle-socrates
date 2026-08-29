"""循证文献检索三件套：Europe PMC + OpenAlex + Crossref（全部免 key）。

用法:
  python search_papers.py "protein intake muscle hypertrophy" [--max 8] [--source all|europepmc|openalex|crossref]
  python search_papers.py fulltext PMC1234567 [--out 全文.txt]   # Europe PMC OA 全文（深挖档用）
  （--out 时写 UTF-8 文件；stdout 输出 JSON 摘要）

统一输出字段: title/authors/year/journal/doi/pmid/pmcid/cited_by/oa/abstract/source/url。
单源失败不影响其他源（错误写进该源槽位）。本机 PubMed E-utilities 被 DNS 污染，禁用。
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import apilib  # noqa: E402

EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPEPMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
OPENALEX_SEARCH = "https://api.openalex.org/works"
CROSSREF_SEARCH = "https://api.crossref.org/works"


def _clip(s: str | None, n: int = 1400) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()[:n]


def europepmc(query: str, max_n: int) -> list[dict]:
    j = apilib.http_json(EUROPEPMC_SEARCH, params={
        "query": f"({query}) AND (SRC:MED)", "format": "json",
        "pageSize": max_n, "resultType": "core"})
    out = []
    for r in j.get("resultList", {}).get("result", []):
        ptl = r.get("pubTypeList") or {}
        out.append({
            "source": "europepmc",
            "title": _clip(r.get("title"), 300),
            "authors": _clip(r.get("authorString"), 200),
            "year": r.get("pubYear"),
            "journal": r.get("journalTitle") or "",
            "doi": r.get("doi"),
            "pmid": r.get("pmid"),
            "pmcid": r.get("pmcid"),
            "cited_by": r.get("citedByCount"),
            "oa": r.get("isOpenAccess") == "Y",
            "pubtype": ptl.get("pubType") if isinstance(ptl, dict) else [],
            "abstract": _clip(r.get("abstractText")),
            "url": f"https://europepmc.org/article/{r.get('source', 'MED')}/{r.get('id')}",
        })
    return out


def openalex(query: str, max_n: int) -> list[dict]:
    j = apilib.http_json(OPENALEX_SEARCH, params={"search": query, "per-page": max_n})
    out = []
    for r in j.get("results", []):
        abstract = ""
        inv = r.get("abstract_inverted_index")
        if inv:  # 倒排索引还原摘要
            pos: dict[int, str] = {}
            for word, idxs in inv.items():
                for i in idxs:
                    pos[i] = word
            abstract = " ".join(pos[i] for i in sorted(pos))
        venue = ((r.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        auths = [a["author"]["display_name"] for a in r.get("authorships", [])[:4]
                 if a.get("author", {}).get("display_name")]
        out.append({
            "source": "openalex",
            "title": _clip(r.get("display_name"), 300),
            "authors": ", ".join(auths),
            "year": r.get("publication_year"),
            "journal": venue,
            "doi": (r.get("doi") or "").replace("https://doi.org/", ""),
            "pmid": None, "pmcid": None,
            "cited_by": r.get("cited_by_count"),
            "oa": bool((r.get("open_access") or {}).get("is_oa")),
            "retracted": r.get("is_retracted"),
            "abstract": _clip(abstract),
            "url": r.get("id"),
        })
    return out


def crossref(query: str, max_n: int) -> list[dict]:
    j = apilib.http_json(CROSSREF_SEARCH, params={
        "query.bibliographic": query, "rows": max_n})
    out = []
    for r in j.get("message", {}).get("items", []):
        year = None
        for k in ("published-print", "published-online", "issued"):
            dp = (r.get(k) or {}).get("date-parts") or [[None]]
            if dp and dp[0] and dp[0][0]:
                year = dp[0][0]
                break
        auths = [f"{a.get('given', '')} {a.get('family', '')}".strip()
                 for a in r.get("author", [])[:4]]
        out.append({
            "source": "crossref",
            "title": _clip((r.get("title") or [""])[0], 300),
            "authors": ", ".join(auths),
            "year": year,
            "journal": (r.get("container-title") or [""])[0] if r.get("container-title") else "",
            "doi": r.get("DOI"),
            "pmid": None, "pmcid": None,
            "cited_by": r.get("is-referenced-by-count"),
            "oa": None,
            "type": r.get("type"),
            "abstract": _clip(r.get("abstract")),
            "url": r.get("URL"),
        })
    return out


def fulltext(pmcid: str, out_path: str | None) -> int:
    pmcid = pmcid.upper()
    if not pmcid.startswith("PMC"):
        pmcid = "PMC" + pmcid
    raw = apilib.http_bytes(EUROPEPMC_FULLTEXT.format(pmcid=pmcid))
    xml = raw.decode("utf-8", "replace")
    xml = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", xml, flags=re.S)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml)).strip()
    if out_path:
        pathlib.Path(out_path).write_text(text, "utf-8")
        print(json.dumps({"code": 0, "pmcid": pmcid, "chars": len(text),
                          "written": out_path}))
    else:
        print(json.dumps({"code": 0, "pmcid": pmcid, "chars": len(text), "text": text[:60000]},
                         ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="英文检索式，或子命令 fulltext")
    ap.add_argument("pmcid", nargs="?", help="fulltext 子命令的 PMCID")
    ap.add_argument("--max", type=int, default=8)
    ap.add_argument("--source", default="all",
                    choices=["all", "europepmc", "openalex", "crossref"])
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    apilib.stdout_utf8()
    if a.query == "fulltext":
        if not a.pmcid:
            print(json.dumps({"code": -1, "message": "fulltext 需要 PMCID"}))
            return 1
        return fulltext(a.pmcid, a.out)

    sources = {
        "europepmc": europepmc,
        "openalex": openalex,
        "crossref": crossref,
    }
    if a.source != "all":
        sources = {a.source: sources[a.source]}
    results: dict = {}
    for name, fn in sources.items():
        try:
            results[name] = fn(a.query, a.max)
        except Exception as e:  # noqa: BLE001
            results[name] = [{"error": str(e)}]
    print(json.dumps({"query": a.query, "results": results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
