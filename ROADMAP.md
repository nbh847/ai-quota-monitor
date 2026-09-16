# Roadmap

最后核对：2026-09-16 14:49（北京时间）。

时间戳取自系统命令：`[System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date),
'China Standard Time')`。本机 git bash 无时区数据库，`TZ=Asia/Shanghai date` 会返回
UTC 时间，不可用于填记录；17:15 与 17:53 两条取自源码文件的修改时间，17:58 一条取自
冒烟响应的 `updated_at_epoch` 反推的北京时间。

## 当前阶段

v0.1 已完成并通过软件与实机验收。v0.2 已开始，当前完成智谱 Token 5 小时／每周额度
接入设计，代码尚未实现。v0.2 沿用统一快照和双窗口 OLED 页面，新增独立智谱适配器、
`/api/v1/quotas/zhipu` 端点与第二个 BOOT 页面；MCP 月度额度、模型用量和工具统计不纳入
本版本。

## 已完成

- 2026-09-16 14:49：完成 v0.2 智谱额度接入设计。参考本机 `glm-stats` skill 并执行只读
  真实查询，确认 `TOKENS_LIMIT unit=3` 为 5 小时、`unit=6` 为每周，`percentage` 为已用
  比例，`nextResetTime` 为毫秒时间戳；冻结 Token 双窗口范围、凭据边界、归一化规则、
  状态映射、OLED 导航和验收标准。尚未修改实现代码。

- 2026-09-16 14:10：用户确认 v0.1 后续功能验收全部完成，包括 BOOT、停止 Agent、断网、
  `STALE`、错误响应和恢复；项目状态转为完成。PC 测试与提交前凭据检查复核通过，完成
  文档收尾并删除已验收 Goal 文档。

- 2026-09-16 13:23：完成首轮硬件正常链路验收。修复本地配置包含路径后重新编译烧录，
  串口不再报告 `secrets.h missing`，ESP32-S3 获得局域网地址并输出
  `Agent connected`；OLED 已正常显示 Codex 剩余额度。异常与恢复路径尚未验收。

- 2026-09-16 13:19：修复 Arduino 构建时本地配置误判缺失。`config.h` 先检查同目录
  `secrets.h`，再兼容从草图目录解析的 `../secrets.h`；真实配置仍位于被 Git 忽略的
  `esp32/secrets.h`，未移动、未写入仓库。此前实机串口已稳定复现 WARNING 与占位 Wi-Fi
  重连错误；修复后仍待重新 Verify、Upload 和串口确认。

- 2026-09-16 09:37：修复 Codex 登录态误判。按官方 App Server 协议给只读
  `account/read` 显式传入 `refreshToken=false`；Codex CLI 0.154.0 在省略参数时会返回
  空账号，即使 `codex login status` 显示已登录。新增回归测试锁定请求参数和调用顺序，
  不执行登录、不强制刷新 Token，也不修改认证文件。

- 2026-09-15 20:06：补充 Codex 登录安全红线：Agent 不得自行登录、登出、刷新或修改
  本地认证状态；每次登录操作必须先说明影响并取得用户针对该次操作的二次明确确认，未确认
  时仅允许只读认证检查，认证失效时报告 `auth_required` 并由用户手动登录。

- 2026-09-15 19:39：修复只读 `-fsyntax-only` 自检暴露的两处固件缺陷。`network.h` 与
  `network.cpp` 重命名为 `quota_net.h` 与 `quota_net.cpp`：原文件名与 ESP32 自带的
  `libraries/Network/src/Network.h` 在大小写不敏感的 Windows 文件系统上同名，而固件
  源码目录排在 `-I` 搜索路径之前，`WiFiGeneric.h` 里的 `#include "Network.h"` 解析到了
  固件自己的头文件，连锁引发 `NetworkInterface`、`ArduinoEvents` 等类型缺失，Arduino
  IDE Verify 同样会失败。`copyBounded` 声明为 `(dest, capacity, src)`，但 8 处调用全部
  按 `(src, dest, capacity)` 传参；全仓库仅此一处定义，已把声明改成与调用一致。
- 2026-09-15 19:00：修复验收发现的软件缺陷：App Server 创建或握手失败后继续有限
  退避重试；旧快照在查询失败并超过 3 分钟后进入 `stale`；独立线程持续排空 stderr；
  Agent 下发本地 `updated_at_local` 供 OLED 显示最近同步时间；固件改用标准 FreeRTOS
  mutex，并恢复 U8g2 正常绘制颜色和低额度反白后的颜色状态。
- 2026-09-15 18:35：让 BOOT 按键事件在串口可见。首版服务商列表只有 Codex，
  `appNextProvider()` 是空操作，原实现只在索引变化时打印日志，导致验收项「BOOT
  单次按下只切换一次」没有任何可核对的输出。现在每次事件都打印前后索引与服务商
  ID，实机可以靠日志判断去抖和单次触发是否正确。
- 2026-09-15 18:31：新增 `esp32/config.h`，消除首次 Verify 的硬阻塞。`network.cpp`
  与 `tasks.cpp` 原本 `#include "../secrets.h"`，而该文件被 gitignore、仓库中不存在，
  第一次 Verify 会直接失败在 `secrets.h: No such file or directory`，并挡住后续所有
  真正的编译错误。现在缺失时回落到占位默认值，不再仅因该文件缺失中断 Verify；
  启动时在串口打印一条 WARNING。占位值不是凭据，也无法连接任何设备，整体编译与
  Upload 仍需人工验证。
- 2026-09-15 18:12：补齐页首对 Agent 报告 `unavailable` 状态的显示（`SRC`），使
  显示层与设计文档第 4 节的五取值状态枚举一一对应；此前该状态落入 `OFF`，会把
  "数据源取不到"误报成"设备连不上 Agent"。
- 2026-09-15 17:58：本机 HTTP 冒烟验证通过，同步 README、设计文档和路线图。
- 2026-09-15 17:53：实现 ESP32-S3 固件（网络拉取、字段白名单解析、共享状态、
  BOOT 去抖、三任务调度、OLED 单页布局）。
- 2026-09-15 17:15：实现 PC Agent（App Server 客户端、额度归一化、内存缓存、
  HTTP 只读接口）与 37 项单元测试。
- 2026-09-15 16:42：确认使用 ChatGPT 登录态和 Codex App Server 读取 5 小时、7 天
  额度窗口；确认 PC Agent、ESP32 轮询、OLED 单页布局、过期状态和安全边界。
- 2026-09-15 15:55：建立项目 README、路线图、首版设计草案和项目级 Agent 规则，
  明确 Codex 首版范围、多服务商扩展方向、BOOT 切换入口、数据安全边界和待确认事项。

## 进行中

- v0.2 智谱额度接入：设计已完成，待实现 PC Agent 适配器、HTTP 端点、固件第二服务商
  页面、自动测试与实机回归。

## v0.2 实施清单

- [x] 核对本机 `glm-stats` skill 与真实智谱响应，冻结数据来源和字段口径。
- [x] 明确 v0.2 只显示 Token 5 小时／每周窗口，MCP、模型用量和工具统计不纳入。
- [ ] 实现智谱配置发现、HTTP 客户端、归一化和独立缓存，不输出 Token 或原始响应。
- [ ] 增加 `/api/v1/quotas/zhipu`，并保持 Codex 端点和缓存行为不回归。
- [ ] 固件服务商列表增加 Zhipu，验证 BOOT 双页循环与快照不串页。
- [ ] 补齐凭据、字段、错误、过期、恢复和双服务商隔离的自动测试。
- [ ] 在 Arduino IDE 中重新 Verify、Upload，并完成 Codex／Zhipu 实机回归。
- [ ] 复核提交集不含 Token、真实内网地址、完整原始响应或本地账号配置。

## v0.1 实施清单

以下事项全部完成后，才能将 v0.1 标记为完成并删除对应 Goal 文档：

- [x] 建立 Codex 数据源适配器，不把密码或 Token 写入固件和仓库。
- [x] 建立统一额度快照和数据有效期判断（3 分钟无成功更新即过期）。
- [x] 实现 ESP32-S3 网络获取、OLED 单页布局和基本状态提示。
- [x] 实现 BOOT 按键去抖及服务商页面导航；首版服务商列表仅含 Codex。
- [x] 覆盖数据成功、缺字段、过期、网络断开和服务恢复路径（PC 侧已测；固件侧
      已完成实机验证）。
- [x] 在 Arduino IDE 中 Verify 通过。
- [x] 在 ESP32-S3 实机完成烧录，并验证双窗口页面、进度条、双重置时间、
      SYNC / STALE 切换、BOOT 按键、停止 PC Agent、断网与强制错误响应后的恢复。
- [x] 检查提交集不含 `secrets.h`、真实内网地址、Token、Cookie、原始 App Server
      响应、`docs/drafts/` 与 `goals/`。

## 后续版本

- v0.2：增加智谱 Token 5 小时／每周额度适配器和页面（进行中，设计已完成）。
- v0.3：增加商汤日日新额度适配器和页面。
- v0.4：增加 OpenRouter 免费额度适配器和页面。
- 后续：根据实际使用情况增加其他服务商、多个额度窗口、历史趋势或告警能力；是否
  纳入以及版本顺序待首版稳定后决定。

## 风险与待确认

- Codex 的额度字段、统计窗口和重置时间可能取决于具体账号、产品入口或数据来源，
  不能在没有可靠来源的情况下固定字段含义。
- 不同服务商的额度单位和重置规则可能不同，统一模型必须允许数值、百分比、文本和
  多窗口同时存在。
- v0.1 的 HTTP 接口不设应用层鉴权，只允许在可信局域网使用；如需暴露到不受信任网络，
  必须先增加鉴权与传输保护。
- SH1106 128x64 接线、BOOT 引脚和页面布局已通过实机验收；更换硬件型号后需重新验证。

## 最近验证

- 2026-09-16 14:49：运行本机共享 skill 的
  `node ~/.agents/skills/glm-stats/scripts/query-usage.mjs`，只读请求当前智谱平台成功。
  `quota/limit` 真实返回 `TIME_LIMIT unit=5`、`TOKENS_LIMIT unit=3` 和
  `TOKENS_LIMIT unit=6`；Token 两项分别带 5 小时／每周窗口、已用百分比和毫秒级
  `nextResetTime`。本次只核对接口与字段，没有修改凭据或外部状态；返回的动态用量数值
  不写入项目文档。尚未实现或测试 v0.2 代码。

- 2026-09-16 14:10：用户确认 BOOT、停止 Agent、断网、`STALE`、错误响应及恢复等后续
  功能验收全部通过。提交前复跑 Python 语法检查与 41 项单元测试，全部通过（7.027s）；
  本地真实 `secrets.h`、Goal 和 `.tmp/` 均命中 Git 忽略规则。真实配置泄漏扫描发现并
  移除 ROADMAP 中的内网地址记录，最终提交集复核见本次提交前检查。
- 2026-09-16 13:23：用户在 Arduino IDE 中重新编译并烧录包含路径修复后的固件；实机
  串口输出 `AI Quota Monitor v0.1`、`Tasks started`、有效局域网 IP 和
  `Agent connected`，不再出现本地配置缺失 WARNING；OLED 已正常显示 Codex 剩余额度。
  本次验证覆盖编译、烧录、Wi-Fi、局域网 HTTP、额度解析和正常页面显示，不覆盖 BOOT、
  断网、3 分钟过期、错误响应及恢复。
- 2026-09-16 13:19：根据实机串口复现 `WARNING: esp32/secrets.h missing` 及 Wi-Fi
  占位配置重复连接错误；本地确认 `esp32/secrets.h` 已存在、三项配置均非占位值，后端
  局域网地址的 health 与双窗口额度接口均正常。修复 include 兼容后，
  用 ESP32 Core 3.3.10-cn 与 `xtensa-esp-elf-g++` 14.2.0 对工具链、依赖及 6 个固件翻译
  单元执行只读 `-fsyntax-only` 检查，全部错误文件为空。该检查不链接、不生成固件；新修复
  尚待 Arduino IDE 重新 Verify、Upload 和实机确认 WARNING 消失。
- 2026-09-16 09:37：在 `pc-agent/.venv` 中运行 `py_compile monitor.py quotas.py
  codex_client.py` 与完整单元测试，语法检查通过，41 项测试全部通过（6.964s）。随后在
  正常用户上下文启动修复后的 PC Agent，请求 `GET /api/v1/quotas/codex`，返回
  `status=ok`、`plan=plus`、5H 剩余 86%（重置 `09-16 12:32`）和 7D 剩余 97%
  （重置 `09-22 20:50`），`message=null`；临时 Agent 已停止，端口 8768 无残留监听。
  官方接口依据：https://developers.openai.com/codex/app-server/ 。
- 2026-09-15 20:43：核对当前工作树的待提交集合与 v0.1 提交安全项。
  `git status --porcelain --untracked-files=all` 显示待提交为 `.gitignore`、
  `AGENTS.md`、`CLAUDE.md`、`ROADMAP.md`、`docs/design.md`、`esp32/`、`pc-agent/`
  与已修改的 `README.md`，分支 `master` 与 `origin/master` 无差异，没有任何提交。
  `git check-ignore -v` 确认 `goals/`、`docs/drafts/`、`__pycache__/`、`.tmp/`、
  `esp32/secrets.h` 均被忽略规则命中。全量扫描排除 `.venv` 与 `.tmp` 后：硬编码 IP
  只有 `monitor.py` 的 `0.0.0.0` 绑定和测试里的 `127.0.0.1` 回环，`Token`／`Cookie`
  关键字只出现在注释、敏感字段断言与伪造 `apikey` 类型测试样例中，`WIFI_SSID`、
  `WIFI_PASSWORD`、`QUOTA_AGENT_BASE_URL` 在 `config.h` 与 `secrets.example.h` 中
  全为 `YOUR_*` 占位值。待提交集合不含真实凭据或账号数据。该集合尚未提交，提交前
  需按最终 add 的内容重新核对。
- 2026-09-15 20:38：只读复验 Codex 真实链路。`codex login status` 仍显示 ChatGPT
  登录；用 `.tmp/auth-recheck/probe.py` 启动真实 App Server 并调用 `account/read`
  与 `account/rateLimits/read`，取到与 HTTP 端点等价的响应：`status=ok`、`plan=plus`、
  5H 剩余 46%（重置 `09-15 23:45`）、7D 剩余 0%（重置 `09-19 18:50`）、
  `updated_at_local=20:37`、`age_sec=0.4`。19:06 记录的 `account/read` 空账号不一致
  已消失，真实 5H／7D 链路复验通过。本次 7D 的 0% 首次真实覆盖固件两条路径，静态
  核对：`drawBar` 在 0% 时 `fillW=0`、`fillW > 0` 为假不画填充，只留外框；
  `drawPercent` 反白绘制后恢复 draw color 1，不影响后续窗口。探针在 `finally` 中
  `cache.stop()`，结束时未遗留 App Server 子进程。该检查不编译固件、不烧录。
- 2026-09-15 20:10：在 `pc-agent/.venv` 中复跑 `py_compile monitor.py quotas.py
  codex_client.py` 与 `python -m unittest discover -s tests -q`，语法检查通过，
  40 项测试全部通过（6.968s）。同时只读复核固件 6 个剩余头文件（`config.h`、
  `app_state.h`、`input.h`、`tasks.h`、`ui.h`、`secrets.example.h`）声明与定义一一对应，
  `appSetLinkState`、`appReady` 均有调用点，无孤儿声明；固件过期判定只用
  `esp_timer_get_time()`，源码内没有 NTP、`configTime` 或 `SNTP`，与固件无可信墙钟
  的前提一致。未编译、未烧录。
- 2026-09-15 19:39：用本机已安装的 `xtensa-esp-elf-g++` 14.2.0 对全部 6 个固件翻译
  单元加 `-fsyntax-only` 做只读语法自检，复用 ESP32 Core 3.3.10-cn 的编译 flags、
  宏定义和头文件路径，另编译 2 个包含自检文件；8 项全部通过，失败文件数 0。该脚本
  位于被 gitignore 的 `.tmp/firmware-syncheck/syncheck.sh`，不进入仓库。它只解析并做
  语法与类型检查，不做 Arduino IDE 的 Verify 流程、不链接、不生成可烧录固件，因此
  不能替代 Verify、Upload 和实机验证。
- 2026-09-15 19:06：通过真实 Codex App Server 启动 PC Agent 并请求 HTTP 额度端点；
  HTTP 返回 200，但业务状态为 `auth_required`。进一步只读检查确认该 App Server 的
  `account/read.account` 为 `null`，未读取或输出账号详情和额度数值。与此同时
  `codex login status` 显示 `Logged in using ChatGPT`，两者状态不一致，当前不能把真实
  5H／7D 链路标记为复验通过。
- 2026-09-15 19:00：在 `pc-agent/.venv` 中运行 `pip install -r requirements.txt`、
  Python 语法检查和 `python -m unittest discover -s tests -q`，安装与语法检查通过，
  40 项测试全部通过（6.945s）。新增测试覆盖 App Server 启动失败后重试、查询失败后
  旧快照过期，以及 stderr 持续排空。
- 2026-09-15 19:00：静态核对固件修复：已安装 ESP32-S3 Core 3.3.10-cn 中存在
  `freertos/semphr.h`、`SemaphoreHandle_t` 和 `xSemaphoreCreateMutex`；源码不再引用
  `esp_synchronization.h`、`MutexHandle_t`、`xMutex*` 或 ESP32 本地 Unix 时间换算。
  `uiDraw` 与 `uiDrawBoot` 使用 draw color 1，低额度反白文字绘制后恢复 draw color 1。
  此记录不替代 Arduino IDE Verify 和实机验证。
- 2026-09-15 18:35：复核新增的 BOOT 日志语句。`appProviderIndex()` 返回
  `uint8_t`、`appProviderId()` 返回 `const char*`，两个符号都由 `app_state.h`
  提供且 `tasks.cpp` 已包含该头文件；`Serial.printf` 在同一文件已有使用（任务创建
  失败分支）。`uint8_t` 经变参提升会变成 `int`，已加 `(unsigned)` 强转以匹配
  `%u`。未经过编译。
- 2026-09-15 18:31：`git check-ignore -v` 确认 `esp32/config.h` 未被忽略规则命中
  （可安全提交，且模板内只有占位值）；`esp32/secrets.h`、`docs/drafts/`、`goals/`
  仍被正确忽略。待提交集合中不含 `secrets.h`、Token 或 Cookie。
- 2026-09-15 18:12：在 `pc-agent/` 下重新运行 `python -m py_compile monitor.py
  quotas.py codex_client.py` 通过；运行 `python -m unittest discover -s tests -q`，
  37 项全部通过（6.957s）。
- 2026-09-15 18:12：固件代码仍然未经过任何编译。本开发环境未安装 arduino-cli，
  Verify 与 Upload 需人工在 Arduino IDE 中执行；OLED 版面已静态核对坐标，进度条
  x=40 宽 86 与 x=2 起的文字块不重叠，页脚 baseline 62 在 64 高度内。
- 2026-09-15 17:58：本机启动 `python monitor.py --host 127.0.0.1 --port 8768`，
  `GET /api/v1/health` 返回 `{"ok": true, ...}`；`GET /api/v1/quotas/codex` 返回
  真实登录态下的 `status=ok`、`plan=plus`、5H 与 7D 双窗口（剩余 100% / 8%）、
  `reset_at_local`（`09-15 22:57` / `09-19 18:50`）、`updated_at_epoch` 与
  `age_sec`。响应字段与固件字段白名单逐项一致；7D 的 8% 覆盖了低于 20% 的反白路径。
- 2026-09-15 15:55：检查克隆后的仓库内容，确认初始仓库仅包含 README 和 LICENSE。
