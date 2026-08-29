# 文献管线规范（循证知识问答）

数据源三件套（均免 key，直连可用）：

- **Europe PMC** `www.ebi.ac.uk/europepmc/webservices/rest/` — PubMed 全量 + OA 全文，主力检索源
- **OpenAlex** `api.openalex.org` — 引文数、撤稿标记（is_retracted，接 Retraction Watch）
- **Crossref** `api.crossref.org` — DOI 存在性兜底验证

> **三源精度差异**：OpenAlex 的 `search` 是相关性匹配，**不吃布尔算符**——同一个布尔式，
> Europe PMC/Crossref 精确命中、OpenAlex 只当普通关键词跑偏。需要精确布尔过滤时以
> Europe PMC 结果为准，OpenAlex/Crossref 用来补充引文数与撤稿信息。

本机网络下 PubMed E-utilities 不可用（校园网 DNS 拦截），**禁止使用**。

## 快答档（默认）

> 下文 `$S` = `<技能根>/scripts/socrates.py`（统一命令行入口）。

1. 把问题翻译成英文检索式。**OR 必须用括号括死**，否则 AND 优先级会让检索面整个跑偏：
   写 `(protein supplementation OR protein intake) AND (muscle hypertrophy OR muscle mass)`，
   不要写 `A OR B AND C OR D`。
2. `python "$S" paper "<检索式>" --max 8`
3. 挑 3–5 篇：优先级 Meta分析/系统综述 > RCT > 前瞻队列；>10 年的经典结论可用但注明年份；同结论取证据等级高的。
4. 读摘要（输出的 abstract 字段）。
5. `python "$S" verify <每条DOI或PMID>` — 必须全绿（exit 0）。
6. 按下述格式输出，标置信度。快答**不沉淀** wiki。

## 深挖档

触发：用户要"深入/详细/写个条目"，或快答发现证据冲突。

1. 先把快答 1–5 步跑完。
2. 对 top 2–3 篇有 PMCID 的，`python "$S" paper --fulltext PMCID --out 全文.txt` 读全文：看方法学（样本量、时长、对照设置）、剂量/频率细节、人群适用性。
3. 用 OpenAlex 引文数判断影响面；被引高的争议论文要提反面研究。
4. 写 wiki 条目（`wiki/_知识条目模板.md`），文件名用问题主题（如 `蛋白粉与增肌.md`）。
   **写入前先按关键词扫一遍 `wiki/*.md`（文件名+主题行）**：同一问题换个问法也算同一条目，
   命中近似条目就在原条目追加"更新记录"并刷新引用，不要新建重复条目。
5. 输出正文，末尾告知已沉淀条目。

## 输出格式（快答）

```markdown
**结论**：…（一句话）

**证据**：
- {要点} —— {作者 et al. {年}}，{期刊}；{类型}（DOI: {doi}）
- …

**置信度**：{strong|moderate|emerging} —— {一句话理由}
**注意**：{争议/反方证据/伪科学提示，没有就省略}

> 基于实时文献检索（YYYY-MM-DD），引用已逐条验证；不构成医疗建议。
```

## 反伪科学立场（直接拒绝并给循证替代）

排毒/酸碱体质、燃脂丸与左旋肉碱神化、局部减脂、"代谢损伤"恐吓、过午不食万能论、
汗蒸/裹保鲜膜减脂、电脉冲腹肌贴、盲目生酮。
拒绝话术结构：明确说"该说法缺乏证据" → 给该问题下的循证结论 → 给可执行替代。

## 检索式技巧

- 用英文；中文概念先翻译（蛋白粉→protein supplement/powder，深蹲→squat，减脂→fat loss）。
- 干预类问题可追加 `AND (randomized* OR "meta-analysis")` 提升证据等级；
  安全/剂量类问题同时检索 `adverse effects`、`injury`。
- 一轮检索不理想，换同义词重检 1–2 次，不要硬凑结论。

## 硬中断规则

`socrates.py verify`（或 `verify_citations.py`）exit 2：**不得输出该引用**。撤稿文献只能在"注意/争议"章节
提及且必须标注"已撤稿"。找不到 DOI 的记忆引用 = 编造，删除该引用或重新检索。
