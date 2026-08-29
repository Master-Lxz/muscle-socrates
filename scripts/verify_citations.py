"""引用硬校验：DOI / PMID 是否真实存在、是否撤稿。零记忆引用纪律的执行器。

用法:
  python verify_citations.py 10.1016/j.jsams.2024.xx PMID:12345678 ...
退出码: 0 = 全部通过；2 = 存在 not_found / retracted（管线必须中断，不许带病输出）。
撤稿信息来自 OpenAlex（接入 Retraction Watch 数据）；OpenAlex 不可达时用 Crossref
兜底验存在性，但撤稿状态记为"未核"，输出时需注明。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import apilib  # noqa: E402

OPENALEX_DOI = "https://api.openalex.org/works/doi:{doi}"
CROSSREF_DOI = "https://api.crossref.org/works/{doi}"
EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

RETRACTED_NOTE = "已撤稿（OpenAlex/Retraction Watch）；只可在'争议/反例'章节明确标注撤稿后提及"


def check_doi(doi: str) -> dict:
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())
    res = {"input": doi, "status": "not_found", "title": "", "year": None,
           "journal": "", "note": ""}
    try:
        j = apilib.http_json(OPENALEX_DOI.format(doi=doi))
        res.update({
            "status": "retracted" if j.get("is_retracted") else "verified",
            "title": (j.get("display_name") or "")[:300],
            "year": j.get("publication_year"),
            "journal": ((j.get("primary_location") or {}).get("source") or {}).get("display_name") or "",
            "note": RETRACTED_NOTE if j.get("is_retracted") else "",
        })
    except Exception as e:  # noqa: BLE001
        try:
            it = apilib.http_json(CROSSREF_DOI.format(doi=doi))["message"]
            res.update({
                "status": "verified",
                "title": (it.get("title") or [""])[0][:300],
                "note": f"OpenAlex 不可达（{e}），撤稿状态未核——输出时注明",
            })
        except Exception as e2:  # noqa: BLE001
            res["note"] = f"OpenAlex({e}) / Crossref({e2})"
    return res


def check_pmid(pmid: str) -> dict:
    try:
        j = apilib.http_json(EUROPEPMC_SEARCH, params={
            "query": f"EXT_ID:{pmid} AND SRC:MED", "format": "json", "pageSize": 1})
        hits = j.get("resultList", {}).get("result", [])
        if not hits:
            return {"input": f"PMID:{pmid}", "status": "not_found", "title": "",
                    "year": None, "journal": "", "note": "Europe PMC 无此 PMID"}
        h = hits[0]
        if h.get("doi"):
            res = check_doi(h["doi"])
        else:
            res = {"input": pmid, "status": "verified",
                   "title": (h.get("title") or "")[:300], "year": h.get("pubYear"),
                   "journal": h.get("journalTitle") or "",
                   "note": "无 DOI，仅经 Europe PMC 核实存在"}
        res["input"] = f"PMID:{pmid}"
        return res
    except Exception as e:  # noqa: BLE001
        return {"input": f"PMID:{pmid}", "status": "not_found", "title": "",
                "year": None, "journal": "", "note": str(e)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+", help="DOI（10.xxxx/...）或 PMID（纯数字）")
    a = ap.parse_args(argv)

    apilib.stdout_utf8()
    results = [check_pmid(x) if re.fullmatch(r"\d{5,9}", x) else check_doi(x)
               for x in a.ids]
    bad = [r for r in results if r["status"] != "verified"]
    print(json.dumps({"all_verified": not bad, "results": results}, ensure_ascii=False))
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
