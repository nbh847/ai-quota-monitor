# Roadmap

最后核对：2026-09-17 10:17（北京时间）。

时间戳通过 PowerShell
`[System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId((Get-Date), 'China Standard Time')`
获取。本机 git bash 的 `TZ=Asia/Shanghai date` 在当前会话返回 UTC 时间（时区数据库
未生效），不可直接用于记录；17:15 与 17:53 两条取自源码文件的修改时间，17:58 一条
取自冒烟响应的 `updated_at_epoch` 反推的北京时间。

## 当前阶段

v0.2 已完成并通过软件与实机验收。PC 侧 81 项单元测试、Codex 与智谱真实 HTTP 冒烟
均通过；固件当时的 `-fsyntax-only` 只读语法自检通过，并完成 Arduino IDE 编译、
烧录，以及 Codex／智谱页面、BOOT 双页切换、断网、过期、错误恢复和中文布局实机验收。
智谱 MCP 月度额度、模型用量和工具统计不纳入本版本。额度重置倒计时显示已完成软件与
实机验收；Codex 与智谱均保留绝对重置时间，并显示一位小数剩余时长。

BOOT 切页延迟缺陷已修复并完成全部回归。按键按原始电平持续稳定 20 ms 确认下降沿，
成功入队后立即唤醒 UI；UI 切页后再立即唤醒 NetworkTask，不再等待两个最长 1000 ms
的周期轮询。当前全部 6 个固件翻译单元的 `-fsyntax-only` 检查通过，固件已重新编译、
烧录；连续 12 次短按全部在按键确认的同一毫秒完成 UI 消费，Codex／智谱逐次往返正确，
长按也只产生一次检测和一次切页。

GPIO13 高电平外接按键增强已完成验收。固件为 GPIO0 BOOT 与 GPIO13 分别保留独立的
20 ms 去抖状态，两者稳定按下后进入同一页面切换事件链；原 BOOT 的低电平输入和行为
未改变。当前全部 6 个固件翻译单元的 `-fsyntax-only` 检查通过，新固件已完成 Arduino
IDE 编译和烧录；GPIO13 与 BOOT 各两次单击均在检测的同一毫秒切页，Codex／智谱往返
正确，没有重复触发。GPIO13 长按只产生一次检测和一次切页，增强功能已完成全部验收。

## 已完成

- 2026-09-17 10:17：新增 GPIO13 高电平外接按键，与原 GPIO0 BOOT 共享页面切换功能，
  两颗按键分别独立去抖且长按不重复触发。全部 6 个固件翻译单元语法检查、Arduino IDE
  编译、烧录、GPIO13 与 BOOT 单击双向切页及长按单次触发实机验收均通过。

- 2026-09-17 09:52：修复 BOOT 切页延迟。按键去抖改为稳定电平状态机，按键成功入队后
  立即唤醒 UI，切页后立即唤醒网络任务；固件语法检查、Arduino IDE 编译、烧录、连续
  12 次短按、双页往返和长按单次触发均通过，原有至少 2 秒的切页延迟已消除。

- 2026-09-16 21:49：额度重置倒计时功能完成。Codex `5H`／`7D` 与智谱 `5H`／`1W`
  在原绝对重置时间后分别显示小时／天倒计时；有限负数归零，异常字段安全降级。Python
  语法检查、PC Agent 81 项单测、固件 `-fsyntax-only`、Arduino IDE 编译、Upload 和
  实机显示均通过，用户确认其他相关路径正常。已同步 README，并按规则关闭和清理 Goal。

- 2026-09-16 20:49：用户确认 v0.2 其余实机项目均无问题，断网、3 分钟过期、错误响应、
  恢复和中文布局验收通过。复跑 Python 语法检查与完整单元测试，81 项全部通过（8.585s）；
  `git diff --check` 通过，`pc-agent/config.json` 与 `esp32/secrets.h` 均被 Git 忽略，未发现
  Token 或真实内网地址进入变更集。v0.2 状态转为完成，并按规则删除已验收 Goal 文档。

- 2026-09-16 20:47：用户确认 BOOT 双页切换正常，Codex 与智谱页面循环导航实机验收
  通过。该结果不覆盖断网、3 分钟过期、错误响应及恢复路径。

- 2026-09-16 20:44：用户确认 ESP32-S3 的 OLED 已正常显示智谱剩余额度，v0.2 正常链路
  实机验收通过。该结论覆盖当前固件烧录、Wi-Fi、PC Agent、智谱真实额度解析和页面显示；
  不覆盖 BOOT 双页循环、断网、3 分钟过期、错误响应、恢复及中文布局细节。

- 2026-09-16 19:28：使用本地 `pc-agent/config.json` 完成智谱真实只读查询，归一化结果
  包含 `5H` 与 `1W` 两个窗口。随后启动 PC Agent 做双端点冒烟：health 返回 v0.2.0，
  Codex 返回 `status=ok` 与 `5H`／`7D`，智谱返回 `status=ok` 与 `5H`／`1W`；未记录
  Token、原始响应或动态额度数值，临时 Agent 已停止。

- 2026-09-16 19:13：将智谱凭据改为项目本地配置。PC Agent 只读取被 Git 忽略的
  `pc-agent/config.json`，仓库提供无真实凭据的 `pc-agent/config.example.json`；不再读取
  QClaw、Claude Code 或进程环境变量。同步重写配置测试并复跑 Python 语法检查与完整
  单元测试，81 项全部通过（8.598s）。

- 2026-09-16 17:39：v0.2 PC Agent 与固件代码实施完成。新增 `zhipu_client.py`
  （智谱 HTTPS 查询、归一化；配置路径已在 19:13 调整）、`zhipu_quotas.py`（独立缓存调度），
  `quotas.py` 提取 `BaseQuotaCache` 公共骨架（v0.1 行为不变），`monitor.py` 装配
  双服务商并新增 `/api/v1/quotas/zhipu`，health 版本升至 0.2.0。固件服务商列表扩为
  `Codex -> Zhipu`，每服务商独立快照与链路状态，BOOT 单步循环，切页立即拉取新页
  且旧响应只提交回旧页，智谱页首用 `u8g2_font_wqy12_t_gb2312a` 按 UTF-8 绘制中文
  「智谱」并恢复英文字体。Python 81 项测试全部通过；固件 `-fsyntax-only` 自检
  7 个翻译单元失败文件数 0。中文字形存在性已用 Python 解析字体数据确认含
  「智」U+667A 与「谱」U+8C31。Arduino IDE Verify/Upload 与实机验收尚未完成。

- 2026-09-16 16:23：将 v0.2 智谱查询参考脚本快照保存到
  `goals/references/glm-query-usage.mjs`，并把 Goal 的外部 Skill 路径改为仓库内相对路径；
  另一台电脑无需安装 `glm-stats` skill 即可核对配置发现、请求端点、认证头和 `unit`
  映射。该文件只作施工参考，生产链路仍须使用项目原生 Python 实现。

- 2026-09-16 16:05：调整 Goal 文档生命周期：`goals/` 不再被 Git 忽略，开发期间纳入
  版本控制；全部验收完成并将结果同步到路线图后删除，施工过程继续由 Git 历史保留。

- 2026-09-16 16:01：清理已从 Git 跟踪中移除的 `docs/` 设计文档引用；项目级规范改为
  由本地 Goal 保存版本设计，`README.md` 与 `ROADMAP.md` 保存可提交的当前事实和进度。

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
## 进行中

- 当前无进行中事项。

## 待处理

- 当前无其他独立待处理事项。

## v0.2 实施清单

- [x] 核对本机 `glm-stats` skill 与真实智谱响应，冻结数据来源和字段口径。
- [x] 明确 v0.2 只显示 Token 5 小时／每周窗口，MCP、模型用量和工具统计不纳入。
- [x] 实现智谱项目本地配置、HTTP 客户端、归一化和独立缓存，不输出 Token 或原始响应。
- [x] 增加 `/api/v1/quotas/zhipu`，并保持 Codex 端点和缓存行为不回归。
- [x] 固件服务商列表增加 Zhipu，并通过 BOOT 双页循环与快照隔离实机验收。
- [x] 补齐凭据、字段、错误、过期、恢复和双服务商隔离的自动测试。
- [x] 在 Arduino IDE 中完成编译、烧录和 Codex／Zhipu 实机回归。
- [x] 复核变更集不含 Token、真实内网地址、完整原始响应或本地账号配置。

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

- v0.2：智谱 Token 5 小时／每周额度适配器和页面（已完成）。
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

- 2026-09-17 10:17：用户确认 GPIO13 长按期间只触发一次页面切换，没有连续事件；结合
  10:13 的 GPIO13／BOOT 单击双向切页日志，GPIO13 外接按键增强通过全部实机验收。

- 2026-09-17 10:13：用户提供新固件实机串口日志。GPIO13 两次单击分别完成
  `Codex -> Zhipu` 与 `Zhipu -> Codex`，随后原 BOOT 两次单击完成相同往返；四组
  `detected` 与 `PAGE event` 时间戳分别完全一致，没有重复事件，确认两颗按键的单击
  去抖、零轮询等待切页和原 BOOT 回归通过。本次日志未覆盖 GPIO13 长按。

- 2026-09-17 10:05：GPIO13 高电平外接按键的软件实现完成。GPIO0 保持 `INPUT_PULLUP`
  与低电平按下，GPIO13 使用 `INPUT_PULLDOWN` 与高电平按下；两颗按键使用独立 20 ms
  去抖状态并共享页面切换事件。使用 ESP32 Core 3.3.10-cn 与 `xtensa-esp-elf-g++`
  14.2.0 对全部 6 个固件翻译单元执行 `-fsyntax-only`，失败文件数 0。该检查不链接、
  不生成固件，不能替代 Arduino IDE Verify、Upload 和实机按键验收。

- 2026-09-17 09:52：用户执行长按回归，整个长按过程只输出一组
  `BOOT detected: t=160406` 与 `BOOT event: t=160406 provider 0 -> 1 (zhipu)`；确认长按
  只切换一次，且按键确认到 UI 消费的时间差为 0 ms。结合此前短按和连续按结果，本次
  BOOT 切页缺陷通过全部实机验收并关闭。

- 2026-09-17 09:50：用户重新编译、烧录修复后的固件并提供串口日志。设备正常启动，
  中文字形检查 `zhi=12 pu=12`，Wi-Fi 与 Agent 连接正常；从 `t=11667` 到 `t=25881`
  连续记录 12 组 `BOOT detected`／`BOOT event`，每组时间戳完全相同，服务商严格按
  Codex／Zhipu 往返，无漏页、重复跳页或可感知延迟。该结果通过短按、连续按和双页
  往返验收；日志未覆盖长按，长按单次触发仍待验证。

- 2026-09-17 09:35：完成 BOOT 切页延迟的软件修复。`input.cpp` 改为每 5 ms 读取原始
  电平并按连续稳定 20 ms 提交状态，只在稳定下降沿产生一次事件；成功入队后用任务通知
  立即唤醒 UiTask，UiTask 切页后再通知 NetworkTask，保留无事件时的 1 秒 UI 刷新与网络
  检查超时。使用本机 ESP32 Core 3.3.10-cn 与 `xtensa-esp-elf-g++` 14.2.0 对当前全部
  6 个固件翻译单元执行 `-fsyntax-only`，失败文件数 0；`git diff --check` 通过。该检查
  不链接、不生成固件，不能替代 Arduino IDE Verify、Upload 和实机时延验收。

- 2026-09-16 22:30：根据用户报告对 BOOT 输入和 UI 调度做静态核对。`input.cpp` 每隔
  至少 20 ms 才接受一次去抖采样，并要求连续两次相同低电平后产生事件；`tasks.cpp` 的
  UI 任务只在每轮绘制前消费事件，随后固定延迟 1000 ms。已确认代码存在短按漏检风险
  和最长约 1 秒的事件消费等待；“偶发数秒”仍需结合带时间戳的串口日志和实机复现定位，
  本次只记录问题，未修改固件、未编译、未烧录。

- 2026-09-16 21:49：用户确认额度重置倒计时的其他相关表现正常，同意标记为开发完成。
  综合此前 PC Agent 81 项单测、固件语法检查、Arduino IDE 编译、Upload 和实机显示结果，
  本功能通过最终验收；Goal 已关闭。

- 2026-09-16 21:47：用户确认额度重置倒计时固件已成功上传到开发板，剩余时间正常显示。
  该结果覆盖 Arduino IDE 编译、Upload 和当前页面正常显示；未明确区分 Codex／智谱页面，
  也未单独覆盖轮询递减、BOOT、断网、过期、错误响应及恢复，相关 Goal 暂不关闭。

- 2026-09-16 21:32：修复额度倒计时负数边界与 Goal 不一致的问题。固件解析有限的
  `reset_in_sec <= 0` 时统一保存为 0，使已映射窗口显示 `(0.0h)`／`(0.0d)`；超过
  `uint32_t` 上限、非有限值及非数值类型仍按无效字段降级。复跑 Python 语法检查与
  PC Agent 81 项单元测试，并对改动涉及的 `quota_net.cpp`、`ui.cpp` 执行 ESP32 Core
  `-fsyntax-only` 检查；结果均通过。该检查不替代 Arduino IDE Verify 和实机验收。

- 2026-09-16 21:23：额度重置倒计时代码实施完成。固件 `models.h` 增加
  `resetInSec`／`hasResetInSec`，`quota_net.cpp` 严格解析 `reset_in_sec`，
  `ui.cpp` 按 `5H`→小时、`7D`／`1W`→天格式化一位小数并组合绘制重置行。PC Agent
  81 项单测全部通过（8.594s），`py_compile` 通过；固件 `-fsyntax-only` 自检 7 个
  翻译单元失败文件数 0（不替代 Arduino IDE Verify）。`git diff --check` 通过。
  尚待 Arduino IDE Verify/Upload 与实机验收。

- 2026-09-16 20:49：用户确认 v0.2 剩余实机项目均无问题；断网、过期、错误恢复和中文
  布局通过。复跑 Python 语法检查与 81 项单元测试，全部通过（8.585s）；`git diff --check`
  通过，真实 PC 与 ESP32 配置均被 Git 忽略，敏感字面量扫描未发现 Token 或真实内网地址。

- 2026-09-16 20:47：用户确认 BOOT 双页切换没有问题，双服务商页面导航实机通过。

- 2026-09-16 20:44：用户确认 OLED 已正常显示智谱剩余额度。正常链路实机结果通过；
  BOOT、断网、过期、错误响应、恢复和中文布局细节仍待单独验收。

- 2026-09-16 19:28：直连智谱额度接口成功，配置来源为项目本地配置，计划字段可解析，
  窗口标签为 `5H`、`1W`。完整 PC Agent HTTP 冒烟同时确认 health v0.2.0、Codex
  `status=ok`（`5H`、`7D`）与智谱 `status=ok`（`5H`、`1W`）。未输出或记录动态额度、
  Token 和完整原始响应，测试进程已停止。

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
  `AGENTS.md`、`CLAUDE.md`、`ROADMAP.md`、本地设计文档、`esp32/`、`pc-agent/`
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
