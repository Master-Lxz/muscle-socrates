---
name: muscle-socrates
description: 肌格拉底：循证健身知识问答 + 训练动作教学视频归纳。凡用户问健身知识（蛋白粉、增肌、减脂、有氧、恢复、睡眠、补剂、训练计划、动作标准等，中英文均可：protein powder、whey、squat、bench press、deadlift、fat loss、cardio 同样触发）或提到具体训练动作（深蹲、卧推、硬拉、划船、引体向上等怎么练/哪个UP主教得好），即使用户没说"肌格拉底"也应触发。知识问题→文献管线（Europe PMC/OpenAlex/Crossref 实时检索，零记忆引用）；动作问题→视频管线（B站 API + 抖音浏览器，归纳国内博主教学要点并附跳转链接）。两条管线互相校验，结果沉淀进 wiki/ 条目。
---

# 肌格拉底（muscle-socrates）

> 未经检索的结论不值得信。

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
深挖结果按 `wiki/_知识条目模板.md` / `wiki/_动作条目模板.md` 沉淀。**写新条目前先按关键词扫一遍
`wiki/*.md`（文件名+主题行），命中近似条目就在原条目追加"更新记录"、不要开新文件**——否则同一个
问题换个问法就会重复建条，wiki 越用越散。条目超 90 天提示可重跑更新（`status` 会直接列出过期条目）。

## 铁律（两条管线共用）

1. **零记忆引用**：每条文献引用必须来自本次实时检索结果，禁止凭记忆写 DOI/标题/作者。
2. **先读后引**：至少读过摘要才能引用；引用前必须跑 `socrates.py verify`，
   返回 exit 2（找不到或撤稿）→ 中断修复，不许带病输出。
3. **置信度分级**：strong（Meta分析/多RCT一致）/ moderate（少量RCT或观察性证据）/
   emerging（初步或机制性证据）。证据薄弱时明说。
4. **视频教学 ≠ 医疗建议**；红旗症状（胸痛、晕厥、持续麻木、关节红肿发热等）一律建议就医。
5. **安全红线**：不建议低于男 1500 / 女 1200 大卡/天的饮食；减重速度 >1kg/周 提示风险。
6. **伪科学直接拒绝**并给循证替代：排毒、燃脂丸、局部减脂、"代谢损伤"恐吓、酸碱体质、电脉冲腹肌贴等。
7. **时效标注**：视频内容必带检索日期（视频可能被删）；文献带年份。

## 一行命令速查（统一入口）

所有功能从**一个入口**走，先解析一次技能根（= 本 SKILL.md 所在目录），之后全部用绝对路径
（`$S` 变量写法适用于 bash / Git Bash；PowerShell 环境直接写完整路径）：

```bash
S="<技能根>/scripts/socrates.py"        # 把 <技能根> 换成 SKILL.md 所在目录

python "$S" status                                              # ① 动作管线 / 首次接手先体检（纯知识快答可跳过，直接②）
python "$S" paper "protein intake hypertrophy" --max 8          # ② 三源文献检索（Europe PMC+OpenAlex+Crossref）
python "$S" paper --fulltext PMC1234567 --out 全文缓存.txt       #    深挖档读全文
python "$S" verify <DOI或PMID>...                               # ③ 引用硬校验（exit 2 = 有问题，必须中断）
python "$S" bili-login                                          # ④ B站扫码登录（首次一次）
python "$S" bili-search "深蹲 教学" --author 凯圣王 --limit 20    # ⑤ B站搜索（支持 --author 过滤白名单UP）
python "$S" bili-fetch BV1xxx BV2yyy                            # ⑥ 抓素材包（可多个BV；默认落盘 .cache/ 只回摘要，--out - 才打印全文）
python "$S" douyin check                                        # ⑦ 抖音登录态；to-playwright OUT / from-playwright SRC 同理
```

各子功能也保留独立脚本（`scripts/` 下同名 `.py`，可单独运行），但一律推荐统一入口。
依赖：标准库为主；`qrcode` 在 bili-login 时自动补装；`brotli` 仅个别弹幕节点需要（脚本会明确提示）。

## UP主白名单

`config/creators.json`：当前偏好 **凯圣王、谭成义**，其余待定（用户后续补充）。
视频结果按"白名单优先 → 播放/互动质量"重排；白名单**不排他**，优质内容照收并标注来源。
搜索命中白名单作者时，把其 uid 回填进 creators.json（防重名误配）。

## 一次性初始化（各做一次，之后免维护）

- **B站**：`python "$S" bili-login`，用户用B站APP扫码（AI字幕必需登录态）。
- **抖音**：用户在任意浏览器（ZCode 内置浏览器或其他 agent 的浏览器均可）扫码登录一次，
  cookie 按规范存 `credentials/douyin_cookies.json`——详见 references/douyin.md。

初始化前可先 `python "$S" status` 看缺什么。
