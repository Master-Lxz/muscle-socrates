# muscle-socrates 肌格拉底

> 未经检索的结论不值得信。

ZCode 技能：**循证健身知识问答**（仿 [grounded](https://github.com/jostelzer/grounded)：检索真实文献、逐条验证引用，零凭记忆编造）+ **训练动作教学视频归纳**（B站 API + 抖音浏览器，汇总国内博主教学，附跳转链接）。两条管线互相校验，结果沉淀为本地 wiki 条目，越用越厚。名字取自"苏格拉底"——什么都先问一句：研究怎么说？

## 功能

1. **知识问答**：Europe PMC + OpenAlex + Crossref 三源检索（全免 key），快答/深挖两档，置信度分级（strong/moderate/emerging），引用先验证再输出。
2. **动作教学归纳**：B站搜索 → AI字幕/弹幕爆点/高赞评论 → 归纳教学要点；抖音走浏览器读平台 AI 总结 + 评论区。UP主白名单优先（当前偏好：凯圣王、谭成义）。
3. **沉淀层**：`wiki/` 存知识条目与动作条目，先查条目再跑管线。

## 安装（ZCode / 其他 agent 通用）

把本仓库克隆到 agent 的技能目录即可：

```bash
git clone https://github.com/Master-Lxz/muscle-socrates.git ~/.agents/skills/muscle-socrates
# ZCode 也支持 ~/.zcode/skills/muscle-socrates
```

脚本为 Python 标准库为主（3.10+）：B站登录时自动补装纯 Python 包 `qrcode`（终端出二维码）；
弹幕解压已兼容B站当前的"裸 deflate"格式，如遇 brotli 节点按脚本提示 `pip install brotli`（可选）。

## 一次性初始化

| 平台 | 动作 | 产物 |
|---|---|---|
| B站 | `python scripts/bilibili_login.py`，B站APP 扫码 | `credentials/bilibili.json`（SESSDATA 等） |
| 抖音 | 任意浏览器打开 douyin.com 扫码登录，导出 cookie | `credentials/douyin_cookies.json`（跨 agent 规范格式，见 references/douyin.md） |

两个平台各自登录一次，之后免维护；cookie 过期重跑登录即可。

## 使用示例

在 agent 对话里直接说：

- "蛋白粉到底有没有用？" → 文献管线快答
- "深蹲膝盖要不要过脚尖？凯圣王是怎么教的？" → 视频管线 + 文献校验，输出要点与跳转链接
- "把卧推写成一个词条" → 深挖档 + 视频归纳 → 沉淀 `wiki/卧推.md`

## 目录结构

```
fitness-wiki/
├── SKILL.md                 # 入口 + 触发路由 + 铁律
├── scripts/
│   ├── apilib.py            # 公共 HTTP（纯标准库）
│   ├── search_papers.py     # Europe PMC / OpenAlex / Crossref 检索 + OA 全文
│   ├── verify_citations.py  # DOI/PMID 存在性 + 撤稿校验（exit 2 = 硬中断）
│   ├── bili_lib.py          # B站 Cookie 持久化 / wbi 签名 / 弹幕解析
│   ├── bilibili_login.py    # 扫码登录 → credentials/bilibili.json
│   ├── bilibili_search.py   # wbi 签名搜索
│   ├── bilibili_fetch.py    # 字幕/弹幕爆点/高赞评论素材包
│   └── douyin_cookies.py    # 抖音 cookie 校验与跨格式转换
├── references/
│   ├── knowledge.md         # 文献管线规范
│   ├── movement.md          # 视频管线规范
│   └── douyin.md            # 抖音浏览器通用方案（不绑定特定浏览器工具）
├── config/creators.json     # UP主白名单（凯圣王、谭成义；uid 首次命中回填）
└── wiki/                    # 沉淀层：_知识条目模板 / _动作条目模板 + 生成条目
```

## 安全与免责

- 不构成医疗建议；红旗症状（胸痛、晕厥、持续麻木、关节红肿发热）一律建议就医。
- 最低热量红线（男 1500 / 女 1200 大卡/天）、减重速度上限（≤1kg/周）。
- 直接拒绝排毒、燃脂丸、局部减脂、"代谢损伤"等伪概念。
- `credentials/` 已被 .gitignore 排除，任何凭证不要提交或分享。

## 已知环境约束

- 本项目开发环境 DNS 污染了 github.com / api.github.com / PubMed E-utilities，
  故文献源使用 Europe PMC 替代 PubMed；仓库经 GitHub API 通道上传。
- B站 AI 字幕需扫码登录；抖音搜索未登录被登录墙拦截，浏览器路线为已实测正解。
