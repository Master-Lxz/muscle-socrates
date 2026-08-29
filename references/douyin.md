# 抖音路线（浏览器通用方案）

## 设计原则：能力无关

抖音网页版未登录搜不了（登录墙实测），AI 总结无公开接口。已验证可行的路线是
**浏览器内流程自动化**：登录一次 → 打开视频页 → 读"AI 总结"面板 → 抓评论区。

本技能**不绑定任何浏览器工具**。无论 agent 手里是什么——ZCode 内置浏览器、
Playwright / Playwright MCP、Chrome DevTools MCP、puppeteer/CDP，甚至人肉操作——
按下面流程执行即可。agent 之间唯一共享的状态是 **cookie 规范文件**。

## 凭证规范（跨 agent 通用）

规范文件：`credentials/douyin_cookies.json`

```json
{"updated": "2026-08-29T12:00:00",
 "cookies": [{"name": "sessionid_ss", "value": "…", "domain": ".douyin.com",
              "path": "/", "expires": 1790000000.0}]}
```

统一入口（`$S` = `<技能根>/scripts/socrates.py`）的 `douyin` 子命令负责校验与互转：

| 子命令 | 用途 |
|---|---|
| `python "$S" douyin check` | sessionid/sessionid_ss 存在且未过期、ttwid 存在 → 有效 |
| `python "$S" douyin to-playwright <out>` | 转 Playwright storage_state，Playwright 系 agent `new_context(storage_state=out)` 直接用 |
| `python "$S" douyin from-playwright <in>` | 从 Playwright `context.cookies()` 导回规范文件 |
| `python "$S" douyin from-netscape <in>` | 从浏览器插件导出的 cookies.txt 导入 |

其他浏览器工具的注入方式：

- **Playwright / Playwright MCP**：先 `to-playwright` 转换，再作为 storage_state / `context.add_cookies()`
- **ZCode 内置浏览器 / browser-use**：`check` 确认有效后，把 cookies 逐条注入该工具的 cookie 设置接口
- **puppeteer / CDP**：`page.setCookie(...)` 逐条注入
- **无浏览器但有 cookie 的脚本流**：不要硬闯 API——搜索接口要 A_Bogus 签名 + 风控，公开 cookie 过不了

## 一次性登录（任何浏览器工具）

1. 打开 `https://www.douyin.com/`
2. 出现登录框/登录墙时停下，**请用户用抖音 APP 扫码**（本路线唯一必须人工的一步）
3. 登录成功后立即导出 cookies 存入规范文件：
   - Playwright 系：`context.cookies()` → 存临时 JSON → `python "$S" douyin from-playwright 临时.json`
   - 其他工具：导出成 Netscape cookies.txt → `python "$S" douyin from-netscape cookies.txt`；或直接按规范格式写 JSON
4. `python "$S" douyin check` 确认 valid

cookie 通常数周后过期：`check` 失败 → 回到第 1 步重新扫码。

## 每次执行流程

1. `python "$S" douyin check` → 无效先走登录
2. 把 cookies 注入当前浏览器
3. 打开搜索 `https://www.douyin.com/search/{URL编码的"动作名 教学"}?type=video`
4. 有新手引导/青少年模式弹窗就关掉
5. 挑前 2–3 个视频（白名单UP优先）：记录作者、标题、点赞数、视频链接（`https://www.douyin.com/video/{id}`）
6. 逐个打开视频页：
   - 点 **"AI 总结"**（入口文案常见"AI总结/看AI总结/总结一下"，面板有分段要点）→ 摘录要点
   - 没有 AI 总结入口 → 用高赞评论代替
   - 向下滚动评论区，读前 20–30 条：点赞数 + 文本，重点看教练/从业者视角的纠错评论
7. 关闭浏览器，按 movement.md 归纳（术语校对：ASR 错别字用常识+评论修正）

> DOM 细节说明：抖音前端 class 名是构建期混淆的，不要依赖具体 class；
> 用**可见文本/aria/role** 定位（如找含"AI 总结"字样的按钮），滚动用页面级滚动。

## 降级与边界

- **agent 完全没有浏览器能力**：明说"抖音路线需要浏览器（登录态是浏览器 cookie）"，
  给选项：a) 用户在自己浏览器登录抖音后用 cookie 插件导出 → `from-netscape` 导入；
  b) 本轮只出 B站结果。
- **视频被删/失效**：条目标"已失效（最后确认 YYYY-MM-DD）"，不删历史记录。
- **不要**为绕过登录去调第三方下载 API（仍需 cookie 且非官方、随时失效）；
  用户未来明确要求时，可评估 Evil0ctal/Douyin_TikTok_Download_API 仅作只读详情/评论补充。
- `credentials/` 永不进 git、不外发、不在对话中回显完整 cookie 值。
