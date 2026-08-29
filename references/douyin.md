# 抖音路线（浏览器通用方案）

## 设计原则：能力无关

抖音网页版未登录搜不了（登录墙实测），AI 总结无公开接口。已验证可行的路线是
**浏览器内流程自动化**：登录一次 → 打开视频页 → 读"AI 总结"面板 → 抓评论区。

本技能**不绑定任何浏览器工具**。无论 agent 手里是什么——ZCode 内置浏览器、
Playwright / Playwright MCP、Chrome DevTools MCP、puppeteer/CDP，甚至人肉操作——
按下面流程执行即可。agent 之间唯一共享的状态是 **cookie 规范文件**。

## 可见性纪律：登录可见，干活后台

用户要的是"我提问，你给答案"，**不是一个一直挂在前台的抖音页面**。硬性纪律：

- **唯一需要可见窗口的时刻**：扫码登录那半分钟（用户要对着屏幕扫）。
- 登录确认、cookie 存盘后，**立即关闭登录窗口/标签页**——不恋战。
- **抓取会话默认后台**：能无头就无头，不能无头就最小化/收起面板。
- **收尾必关的是"可见窗口"**：本次打开的搜索页/视频页全部关掉，不留任何前台窗口。
- **headless 常驻会话可以保留**（如 agent-browser 的 `--session douyin`）：它没有窗口、
  能跨对话复用登录态；但临时会话和可见窗口必须 finally 里正常 close，避免僵尸 Chromium。
- 例外：用户明确说"我想看着你操作"时才保持可见。

各工具落地：

- **ZCode 内置浏览器 / browser-use**：用它的可见性能力在抓取阶段收起面板；登录 tab 扫完码即关；
  收尾时关闭本次打开的所有 tab 并结束会话
- **Playwright / Playwright MCP**：推荐**两段式**——登录用有头短会话（把二维码亮给用户扫），
  抓取用**无头**新会话加载 storage_state；会话用完 `context.close()`
- **puppeteer / CDP**：同上，抓取走 headless
- **人肉/半自动**：只请用户在扫码时看一眼屏幕，其余步骤不要在用户面前翻页

## 推荐实现（agent-browser 版速查）

技能保持能力无关；如果你手里的工具是 agent-browser，这是踩坑后整理的开箱即用路径：

```bash
# ① 常驻会话：headless + 持久命名 session，跨对话复用登录态，默认无弹窗
agent-browser --session douyin open "https://www.douyin.com"

# ② 首次登录：临时切 headed 把二维码亮给用户；确认登录 → 导出 cookie 到规范文件 → 关掉可见窗口
agent-browser --session douyin --headed open "https://www.douyin.com"

# ③ 抓取一律 snapshot 读内容（不要用 eval，原因见"已踩过的坑"）
agent-browser --session douyin snapshot
agent-browser --session douyin open "https://www.douyin.com/search/深蹲 教学?type=video"

# ④ 收尾：可见窗口与临时会话 finally 里必关；--session douyin 常驻保留以复用登录态，
#    同一 session 名只留一个 daemon，防僵尸 Chromium
agent-browser --session douyin close
```

Windows 下 Chromium 下载被证书拦截时：设 `AGENT_BROWSER_EXECUTABLE_PATH` 指向本机 Chrome。

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
- **持久 session vs 规范文件**：`--session douyin` 这类持久会话是**单个工具**的登录态载体，
  cookie 规范文件才是**跨工具交换的唯一格式**——登录确认后尽量两边都落（session 保活 + 导出规范文件）

## 一次性登录（任何浏览器工具）

1. 打开 `https://www.douyin.com/`
2. 出现登录框/登录墙时停下，**请用户用抖音 APP 扫码**（本路线唯一必须人工的一步）
3. 登录成功后立即导出 cookies 存入规范文件：
   - Playwright 系：`context.cookies()` → 存临时 JSON → `python "$S" douyin from-playwright 临时.json`
   - 其他工具：导出成 Netscape cookies.txt → `python "$S" douyin from-netscape cookies.txt`；或直接按规范格式写 JSON
4. `python "$S" douyin check` 确认 valid
5. **立即关闭登录用的窗口/标签页**——扫码是唯一需要可见屏幕的步骤，确认登录后就该收起，
   后续所有抓取在后台会话跑（见"可见性纪律"）

cookie 通常数周后过期：`check` 失败 → 回到第 1 步重新扫码。

## 每次执行流程

0. **先定可见性**：抓取会话默认后台（无头/收起面板）；只有走到登录步骤才切可见
1. `python "$S" douyin check` → 无效先走登录
2. 把 cookies 注入当前浏览器
3. 打开搜索 `https://www.douyin.com/search/{URL编码的"动作名 教学"}?type=video`
4. 有新手引导/青少年模式弹窗就关掉
5. 挑前 2–3 个视频（白名单UP优先）：记录作者、标题、点赞数、视频链接（`https://www.douyin.com/video/{id}`）
6. 逐个打开视频页：
   - 点 **"AI 总结"**（入口文案常见"AI总结/看AI总结/总结一下"，面板有分段要点）→ 摘录要点
   - **AI 总结面板在跨域 iframe 里**：`eval`/页面内 JS 因同源策略拿不到它——拿不到 ≠ 总结不存在。
     Playwright 系用 `page.frame_locator()` 读 frame 内文本；agent-browser 用 `snapshot` 读全帧内容；
     两条路都失败才降级用高赞评论，并在输出注明"AI 总结未获取"
   - 向下滚动评论区，读前 20–30 条：点赞数 + 文本，重点看教练/从业者视角的纠错评论
7. **收尾必关**：关掉本次打开的所有搜索页/视频页并结束浏览器会话，不留常驻窗口；
   然后按 movement.md 归纳（术语校对：ASR 错别字用常识+评论修正）

> DOM 细节说明：抖音前端 class 名是构建期混淆的，不要依赖具体 class；
> 用**可见文本/aria/role** 定位（如找含"AI 总结"字样的按钮），滚动用页面级滚动。
> **`eval` 在抖音页面经常失效**（风控注入检测 + AI 总结在跨域 iframe）——抓内容一律用
> snapshot 的文本/引用（agent-browser 用 `snapshot -i`），不要靠注入 JS。

## 已踩过的坑（写给下一个 agent）

| 坑 | 处理 |
|---|---|
| `eval` 在抖音页面失效（风控 + 跨域 iframe） | 定位一律用 snapshot 文本/引用（agent-browser 用 `snapshot -i`）；跨 frame 文本用 Playwright `page.frame_locator()` |
| AI 总结面板在跨域 iframe，eval 拿不到 | 拿不到 ≠ 不存在：换 frame 级读取；实在不行降级"标题+评论"归纳并在输出注明 |
| Windows 下 Chromium 下载被证书拦 | `AGENT_BROWSER_EXECUTABLE_PATH` 指向本机 Chrome |
| daemon/僵尸 Chromium 泄漏 | 同一 session 名只留一个 daemon；临时与可见会话 close 放 finally；多个 chromium 残留就手动清 |
| cookie 是明文 | `credentials/` 别进 dotfiles 同步/备份/网盘；.gitignore 已兜底 |
| 匿名 B站搜索 -412 / v_voucher | 跑一次 `bili-login` 扫码；视频管线要双源（B站+抖音）才算达标 |

## 降级与边界

- **agent 完全没有浏览器能力**：明说"抖音路线需要浏览器（登录态是浏览器 cookie）"，
  给选项：a) 用户在自己浏览器登录抖音后用 cookie 插件导出 → `from-netscape` 导入；
  b) 本轮只出 B站结果。
- **抖音 AI 总结确实拿不到时**：输出注明"AI 总结未获取，依据标题+评论区归纳"，
  并让 B站源（AI 字幕）顶上补齐质量——别默默漏掉这块信息。
- **视频被删/失效**：条目标"已失效（最后确认 YYYY-MM-DD）"，不删历史记录。
- **不要**为绕过登录去调第三方下载 API（仍需 cookie 且非官方、随时失效）；
  用户未来明确要求时，可评估 Evil0ctal/Douyin_TikTok_Download_API 仅作只读详情/评论补充。
- `credentials/` 永不进 git、不外发、不在对话中回显完整 cookie 值。
