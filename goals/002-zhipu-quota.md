# Goal 002：v0.2 智谱 Token 额度监控

创建时间：2026-09-16 15:00（北京时间）
状态：待实施

## 目标

在不回归 v0.1 Codex 功能的前提下，为 PC Agent 和 ESP32-S3 增加智谱 Token 额度支持。
PC Agent 从本机现有智谱配置中只读获取额度，将 5 小时和每周窗口归一化为统一快照；
OLED 增加 Zhipu 页面，BOOT 在 Codex 与 Zhipu 之间单步循环切换。

最终可独立验收的结果是：同一 PC Agent 同时提供 Codex 与 Zhipu 两个只读额度端点，
ESP32-S3 能稳定显示两个服务商各自的数据、异常状态和恢复结果，且服务商之间不串数据。

## 依据与已冻结决策

- 本文件是 v0.2 智谱接入的需求、接口与验收设计源。
- 当前进度与实施清单：[ROADMAP.md](../ROADMAP.md#v02-实施清单)。
- 查询协议参考已随 Goal 纳入仓库的
  [`references/glm-query-usage.mjs`](references/glm-query-usage.mjs)。该文件是本机共享
  `glm-stats` skill 脚本在 2026-09-16 的快照，供另一台电脑离线核对配置发现、端点、
  请求头和字段映射；无需安装该 skill。
- 2026-09-16 已通过该 skill 完成真实只读查询，确认：
  - `TOKENS_LIMIT unit=3` 是 5 小时窗口。
  - `TOKENS_LIMIT unit=6` 是每周窗口。
  - `percentage` 是已用比例。
  - `nextResetTime` 是毫秒时间戳。
  - `TIME_LIMIT unit=5` 是 MCP 月度额度。
- v0.2 只显示 Token 的 `5H` 与 `1W` 两个窗口。MCP 月度额度、模型用量和工具统计不
  纳入本 Goal。
- 智谱 OLED 页首标题冻结为中文「智谱」，不显示英文 `ZHIPU`。只为标题引入所需中文
  字形，其他内容继续使用现有英文字体，避免无关字库扩大固件体积。
- 生产链路使用项目原生 Python 实现，不调用随 Goal 保存的 Node.js 参考快照，不新增
  Node.js 运行时依赖。
- 智谱端点当前没有公开协议文档。未知字段或 `unit` 必须显式降级，禁止靠数组顺序、
  `number` 或重置时间大小推断窗口类型。

## 范围

### 允许修改

- PC Agent：`pc-agent/monitor.py`、现有额度公共逻辑，以及新增的智谱客户端、适配器和
  缓存模块。
- PC 测试：`pc-agent/tests/` 下与智谱客户端、归一化、缓存、HTTP 契约和双服务商隔离
  直接相关的样例与测试。
- ESP32 固件：`esp32/ai-quota-monitor/` 下的服务商注册、分服务商状态、网络拉取、
  BOOT 导航、显示和诊断代码。
- 受事实变化影响的 `README.md`、`ROADMAP.md`、当前 Goal 和项目规范文档。

### 禁止修改或扩大

- 不实现 MCP 月度额度、模型用量、工具统计、历史趋势、告警、多账号和远程配置。
- 不改变 v0.1 Codex 的额度口径、登录安全红线、5H／7D 标签或 HTTP 契约。
- 不把 Token、真实网络地址、完整原始响应、本地账号配置或真实用量样例写入仓库、日志
  或 HTTP 响应。
- 不修改真实 `.env`、`esp32/secrets.h`、Codex 登录态或任何服务商认证状态。
- 不新增第三方依赖，除非标准库和现有依赖无法满足且另行说明必要性。
- 不提交、推送、部署或发布；这些操作需要用户另行明确授权。

## 预期接口与行为

### PC Agent

- 新增 `GET /api/v1/quotas/zhipu`，继续只读内存缓存，不在 HTTP 请求线程内直接查询
  智谱 API。
- 保持 `GET /api/v1/quotas/codex` 和 `GET /api/v1/health` 兼容；健康端点版本更新为
  v0.2。
- 智谱配置发现顺序与参考 skill 一致：
  1. `~/.qclaw/agents/main/agent/models.json` 中匹配智谱域名的 provider。
  2. `~/.claude/settings.json` 的 `env`。
  3. 进程环境变量 `ANTHROPIC_BASE_URL` 与 `ANTHROPIC_AUTH_TOKEN`。
- v0.2 验收域名为 `open.bigmodel.cn` 与 `dev.bigmodel.cn`；`api.z.ai` 未经本项目独立真实
  验证时不得声明支持。
- 使用标准库发起有限超时的 HTTPS GET：
  `/api/monitor/usage/quota/limit`。`Authorization` 直接放 Token，不添加 `Bearer`。
- 只解析 `data.level`、`data.limits[].type`、`unit`、`percentage` 和
  `nextResetTime`；输出统一快照白名单字段。
- `unit=3 -> 5H`、`unit=6 -> 1W`；
  `remaining_percent = clamp(round(100 - percentage), 0, 100)`；毫秒时间戳转换为 Unix
  秒后再计算和格式化时间。
- 智谱缓存每 60 秒轮询一次，180 秒无成功更新后变为 `stale`；失败保留最后有效快照。
- 缺少配置或 HTTP 401／403 为 `auth_required`；网络错误、超时、HTTP 429／5xx 为
  `unavailable`；目标窗口全部无效为 `invalid_data`。
- Codex 与 Zhipu 使用独立状态、快照、调度和停止路径；任一服务商失败不影响另一个。

### ESP32-S3

- 服务商列表固定为 `Codex -> Zhipu`，BOOT 每次稳定按下只前进一页并循环。
- 每个服务商保存独立快照和链路状态。切页时立即显示目标服务商自己的旧值或无数据
  状态，不得短暂显示另一服务商快照。
- 网络任务按当前 provider ID 请求对应端点；切页后应尽快拉取新页面数据，同时保持
  现有正常轮询、失败退避和 Wi-Fi 恢复行为。
- Zhipu 页面沿用双窗口布局，页首用 UTF-8 绘制中文「智谱」，同时显示计划等级、`5H`、
  `1W`、重置时间、进度条、`SYNC`／`STALE` 和统一状态标签。中文标题绘制后必须恢复
  现有英文字体，不能影响其他文字和 Codex 页面。
- Codex 页面布局、低额度反白、3 分钟过期和错误恢复行为保持不变。

## 施工检查点

### 1. 智谱客户端与配置发现

预期结果：项目原生 Python 客户端能从三种来源按优先级获取配置，验证域名并查询
`quota/limit`；任何错误都不泄露 Token 或原始响应。

验证方式：单元测试覆盖三个来源、优先级、损坏 JSON、缺少字段、未知域名、无 Token、
请求头、超时、401／403、429、5xx、无效 JSON 和网络异常。

### 2. 智谱归一化与缓存

预期结果：只输出 `5H` 和 `1W`，比例与时间换算正确；部分窗口缺失可降级，全部无效时
报告 `invalid_data`；缓存能进入 `stale` 并在恢复后回到 `ok`。

验证方式：固定样例覆盖数组乱序、MCP 条目夹在中间、未知 `unit`、百分比边界、NaN、
bool、字符串、无效毫秒时间戳、单窗口、双窗口缺失、查询失败、过期和恢复。

### 3. 双服务商 PC Agent

预期结果：两个缓存独立启动、渲染和停止；两个额度端点同时可用；未知路径仍返回 404；
HTTP 响应不含敏感字段。

验证方式：扩展 HTTP 契约测试，分别断言 Codex 与 Zhipu 响应；模拟单侧失败，确认另一侧
保持 `ok`；确认关闭服务时两个调度线程都收到停止信号且无测试进程残留。

### 4. ESP32 分服务商状态与导航

预期结果：固件注册两个服务商并保存两份独立快照；BOOT 单步循环；切页和拉取期间不
串页；智谱页首正确显示中文「智谱」且无缺字方框；诊断日志能标识当前服务商。

验证方式：从当前安装的 U8g2 库中选择实际包含「智」「谱」字形的中文字体，使用 UTF-8
绘制接口；先做静态调用链检查和只读 `-fsyntax-only` 自检，再在 Arduino IDE 中 Verify、
Upload，通过串口和 OLED 实机检查中文笔画、页首间距、字体恢复与完整页面。

### 5. 端到端与回归

预期结果：真实 Codex 和智谱数据均可经同一 PC Agent 返回并由设备显示；停止或破坏
智谱数据源只影响 Zhipu 页；恢复后自动更新；v0.1 Codex 行为不回归。

验证方式：本机 HTTP 冒烟、完整 Python 测试、敏感信息扫描、Arduino IDE Verify／Upload
和实机异常恢复测试。真实接口查询仅执行只读请求，不改变认证状态。

### 6. 文档与状态收尾

预期结果：实现事实、运行方式、测试数量、实机状态和剩余限制在三份项目文档中一致；
未完成或未验证内容不写成已支持。

验证方式：逐项对照本 Goal 验收标准，运行 `git diff --check`，检查 Git 状态、忽略规则和
待提交集合，不执行 add、commit 或 push。

## 自动验证入口

在 `pc-agent/` 下运行：

```text
.venv/Scripts/python -m py_compile monitor.py quotas.py codex_client.py <新增智谱模块>
.venv/Scripts/python -m unittest discover -s tests -q
```

基线为 v0.1 的 41 项测试。v0.2 可以增加测试，但不得删除或弱化既有断言来换取通过。

固件验证分为两层：

1. 复用本机 ESP32 Core 与 `xtensa-esp-elf-g++` 做只读 `-fsyntax-only` 检查。该结果不能
   替代 Arduino IDE Verify。
2. 在 Arduino IDE 中对 `esp32/ai-quota-monitor/ai-quota-monitor.ino` 执行 Verify 和
   Upload，再完成实机显示、BOOT、断网、过期、错误与恢复验收。

烧录前必须动态确认唯一的 ESP32-S3 串口和芯片型号；无法唯一识别时停止，不猜测端口。

## 关键失败路径

- 配置文件存在但损坏、字段缺失或指向未知域名。
- Token 缺失、失效或接口返回 401／403。
- API 超时、DNS／TLS／网络失败、429 或 5xx。
- 响应不是 JSON、缺少 `data.limits`、窗口类型未知、比例或时间戳非法。
- 两个服务商并发调度时一侧卡住、失败或停止，影响另一侧。
- BOOT 切页时网络任务正在请求旧服务商，旧响应晚到后覆盖当前页。
- Wi-Fi 或 Agent 断开后重新连接，当前页和非当前页状态不一致。
- 固件只保存一份快照，导致 Codex 与 Zhipu 页面串数据。
- 日志、异常、HTTP 响应、测试样例或文档泄露 Token、真实地址或完整原始响应。

## 验收标准

- [ ] PC Agent 原生实现智谱查询，不依赖 Node.js skill 运行时。
- [ ] `/api/v1/quotas/codex` 与 `/api/v1/quotas/zhipu` 同时满足统一快照契约。
- [ ] 真实智谱响应可正确显示 `5H` 和 `1W` 的剩余比例及本地重置时间。
- [ ] MCP、模型用量和工具统计没有进入 v0.2 页面或统一 Token 窗口。
- [ ] Codex 与 Zhipu 的缓存、错误、过期和恢复互不影响。
- [ ] BOOT 在两个服务商间单步循环，切页期间不串数据显示。
- [ ] 智谱页首以中文「智谱」显示，无缺字、截断或重叠，且不影响 Codex 英文页面字体。
- [ ] Python 语法检查和完整单元测试全部通过，既有 41 项测试无回归。
- [ ] Arduino IDE Verify、Upload 和规定的实机异常路径全部通过。
- [ ] `README.md`、`ROADMAP.md`、当前 Goal 与实际状态一致。
- [ ] 最终待提交集合不含凭据、真实网络地址、完整原始响应或本地账号配置。

## 交付结果

Goal 完成时记录以下内容：

- 实际新增和修改的文件。
- 最终 Python 测试数量、执行命令与结果。
- 智谱真实 HTTP 冒烟的字段级结论，不记录动态额度数值和完整原始响应。
- 固件只读语法检查、Arduino IDE Verify／Upload 和实机验收结果。
- 未解决问题、残余风险和后续版本边界。
- `ROADMAP.md` 中的完成状态、北京时间和本 Goal 文件链接。

只有全部验收标准通过后，才能将状态改为“已完成”；尚未完成 Arduino IDE 或实机验证
时必须保持“进行中”。
