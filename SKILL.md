---
name: fitness-wiki
description: 健身百科：循证健身知识问答 + 训练动作教学视频归纳。凡用户问健身知识（蛋白粉、增肌、减脂、有氧、恢复、睡眠、补剂、训练计划、动作标准等）或提到具体训练动作（深蹲、卧推、硬拉、划船、引体向上等怎么练/哪个UP主教得好），即使用户没说"健身百科"也应触发。知识问题→文献管线（Europe PMC/OpenAlex/Crossref 实时检索，零记忆引用）；动作问题→视频管线（B站 API + 抖音浏览器，归纳国内博主教学要点并附跳转链接）。两条管线互相校验，结果沉淀进 wiki/ 条目。
---

# 健身百科（fitness-wiki）

双管线技能：**循证知识问答**（仿 grounded：检索真实文献、验证引用、再归纳）+
**动作教学视频归纳**（B站 API + 抖音浏览器，汇总国内博主教学）。
本地沉淀层 `wiki/` 存条目、越用越厚；**先查条目，再跑管线**。

技能根目录 = 本文件所在目录。脚本在 `scripts/`，凭证在 `credentials/`（git 忽略，勿外发）。

## 第零步：路由

| 用户输入特征 | 走哪条线 | 先读哪个文件 |
|---|---|---|
| 知识/机制/证据问题（"蛋白粉有用吗""减脂缺口多大合适"） | 文献管线 | references/knowledge.md |
| 具体动作怎么练（"深蹲膝盖能不能过脚尖"） | 视频管线 + 文献校验 | references/movement.md |
| 流程涉及抖音 | — | references/douyin.md |
| 混合问题 | 两条都跑，按动作条目模板合并 | 两个都读 |

**先查 `wiki/`**：命中条目直接答（标注"依据 wiki 条目，更新于 YYYY-MM-DD"），没有才跑管线；
深挖结果按 `wiki/_知识条目模板.md` / `wiki/_动作条目模板.md` 沉淀。条目超 90 天提示可重跑更新。

## 铁律（两条管线共用）

1. **零记忆引用**：每条文献引用必须来自本次实时检索结果，禁止凭记忆写 DOI/标题/作者。
2. **先读后引**：至少读过摘要才能引用；引用前必须跑 `scripts/verify_citations.py`，
   返回 exit 2（找不到或撤稿）→ 中断修复，不许带病输出。
3. **置信度分级**：strong（Meta分析/多RCT一致）/ moderate（少量RCT或观察性证据）/
   emerging（初步或机制性证据）。证据薄弱时明说。
4. **视频教学 ≠ 医疗建议**；红旗症状（胸痛、晕厥、持续麻木、关节红肿发热等）一律建议就医。
5. **安全红线**：不建议低于男 1500 / 女 1200 大卡/天的饮食；减重速度 >1kg/周 提示风险。
6. **伪科学直接拒绝**并给循证替代：排毒、燃脂丸、局部减脂、"代谢损伤"恐吓、酸碱体质、电脉冲腹肌贴等。
7. **时效标注**：视频内容必带检索日期（视频可能被删）；文献带年份。

## 脚本速查（标准库为主，无需预装依赖）

依赖说明：B站登录二维码自动补装纯 Python 包 `qrcode`；弹幕解压兼容裸 deflate（当前B站行为），
极少数节点需可选包 `brotli`——脚本会明确提示 `pip install brotli`，装不装都不影响字幕/评论。

```bash
# 文献
python scripts/search_papers.py "protein intake muscle hypertrophy" --max 8
python scripts/search_papers.py fulltext PMC1234567 --out 全文缓存.txt   # 深挖读全文
python scripts/verify_citations.py <DOI或PMID> ...                      # 引用硬校验

# B站（首次先扫码：登录态存 credentials/bilibili.json）
python scripts/bilibili_login.py
python scripts/bilibili_search.py "深蹲 教学" [--author 凯圣王] [--limit 20]
python scripts/bilibili_fetch.py BV1xxx [--out 素材包.json]             # 字幕/弹幕爆点/高赞评论

# 抖音（凭证跨 agent 通用，见 references/douyin.md）
python scripts/douyin_cookies.py check
python scripts/douyin_cookies.py to-playwright state.json               # 给任意 Playwright 系 agent 用
```

## UP主白名单

`config/creators.json`：当前偏好 **凯圣王、谭成义**，其余待定（用户后续补充）。
视频结果按"白名单优先 → 播放/互动质量"重排；白名单**不排他**，优质内容照收并标注来源。
搜索命中白名单作者时，把其 uid 回填进 creators.json（防重名误配）。

## 一次性初始化（各做一次，之后免维护）

- **B站**：跑 `bilibili_login.py`，用户用B站APP扫码（AI字幕必需登录态）。
- **抖音**：用户在任意浏览器（ZCode 内置浏览器或其他 agent 的浏览器均可）扫码登录一次，
  cookie 按规范存 `credentials/douyin_cookies.json`——详见 references/douyin.md。
