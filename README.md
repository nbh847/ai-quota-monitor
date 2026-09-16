# AI Quota Monitor

基于 ESP32-S3 和 OLED 的 AI 服务商额度监控显示器。

项目已完成 Codex 与智谱的剩余额度、重置时间显示，支持通过 BOOT 按键在两个服务商
页面间切换。商汤日日新、OpenRouter 免费额度等服务商列入后续版本。

> 当前状态：v0.2 已完成。PC Agent 的 81 项单元测试与 Codex／智谱真实 HTTP 冒烟
> 均通过；固件已完成 Arduino IDE 编译、烧录，以及双服务商页面、BOOT 切换、断网、
> 过期、错误恢复和中文布局实机验收。

## 项目目标

- 在 OLED 上以低认知成本显示 AI 服务商的额度状态。
- 将不同服务商的数据统一为稳定的额度快照，避免显示层绑定某一家服务商的接口。
- 使用 BOOT 按键切换服务商页面；首版只有 Codex 数据，后续逐步增加其他服务商。
- 将鉴权和敏感配置放在受控的数据来源侧，不把密码、Token 或真实网络地址写入固件
  和仓库。

## 当前范围

### 已确定

- 目标硬件：ESP32-S3 + SH1106 128x64 OLED（I2C，SDA GPIO8 / SCL GPIO9）。
- 目标数据：Codex 5H 与 7D 窗口的剩余额度比例、各自的本地重置时间，以及必要的
  状态提示。
- 交互方式：BOOT 按键切换服务商额度页面。
- 首版服务商：Codex。
- v0.2 目标服务商：智谱，显示 Token 5 小时和每周两个额度窗口。

### 暂不纳入 v0.2

- 智谱 MCP 月度额度、模型调用统计和工具调用统计。
- 商汤日日新额度监控。
- OpenRouter 免费额度监控。
- 多账号管理、历史曲线、告警推送和远程配置后台。
- 未经确认的数据源、鉴权方式或服务商内部接口。

## 页面内容

单页同时显示两个额度窗口，不做翻页：

```text
CODEX   PLUS      OK
5H 80% [████████░░]
R      09-15 17:52
7D 12% [█░░░░░░░░░]
R      09-19 18:50
SYNC          15:55
```

- 进度条由固件用 U8g2 图形调用画出连续矩形，剩余比例低于 20% 时数值反白显示
  但不闪烁。
- 页脚正常显示最近一次成功同步的本地时间 `SYNC HH:MM`，3 分钟没有成功更新后改为
  `STALE Nm`，同时保留上次
  有效数值，不用旧数据伪装成实时数据。
- 页首状态优先反映设备侧连接情况：`WIFI` 连接中、`OFF` 数据服务不可达，否则
  显示 Agent 报告的 `OK` / `LOGIN` / `SRC`（数据源取不到）/ `BAD` / `STALE`。

多个额度窗口各自保留窗口标签和重置时间，不合并成一个数字。

## 数据流

```text
ChatGPT 登录态 → codex_client.py → Codex 独立缓存
pc-agent/config.json → zhipu_client.py → 智谱独立缓存
    ↓
pc-agent/monitor.py        /api/v1/quotas/codex 与 /api/v1/quotas/zhipu
    ↓
esp32 固件                 按当前页面轮询，分服务商保存独立快照
    ↓
SH1106 128x64 OLED         BOOT 切换 Codex／智谱双窗口页面
```

Codex 凭据留在 PC 侧 ChatGPT 登录态，智谱 Key 留在被 Git 忽略的
`pc-agent/config.json`；固件不保存服务商密码或 Token。局域网 HTTP 接口不设应用层
鉴权，只允许在可信局域网使用，不应暴露到公网或不受信任网络。

## 后续服务商

| 服务商 | 计划版本 | 状态 |
| --- | --- | --- |
| Codex | v0.1 | 已完成并通过实机验收 |
| 智谱 | v0.2 | 已完成并通过实机验收 |
| 商汤日日新 | v0.3 | 待调研数据来源和额度口径 |
| OpenRouter 免费额度 | v0.4 | 待调研免费模型和额度口径 |

新增服务商时，应只新增适配器和服务商元数据，尽量不改动 OLED 布局、BOOT 导航和统一
状态模型。

## 硬件与实现状态

固件按 SH1106 128x64 实现，I2C 使用 SDA GPIO8 / SCL GPIO9，BOOT 按键取 GPIO0
（上拉，按下为低电平）。当前接线与页面已通过实机验收。

运行方式：

- PC 侧：进入 `pc-agent/` 后执行 `python -m venv .venv`、
  `.venv/Scripts/python -m pip install -r requirements.txt`，再运行
  `.venv/Scripts/python monitor.py`（默认 `0.0.0.0:8767`，仅标准库，无第三方依赖）。
- 智谱配置：编辑本地 `pc-agent/config.json`，填写 `zhipu.api_key`；该文件已被 Git
  忽略，仓库中的 `pc-agent/config.example.json` 仅作为安全模板。
- 设备侧：在 Arduino IDE 中打开 `esp32/ai-quota-monitor/ai-quota-monitor.ino`，先
  Verify 再 Upload。依赖 U8g2 与 ArduinoJson。
- 本地配置：把 `esp32/secrets.example.h` 复制为 `esp32/secrets.h` 并填写真实值。
  没有 `secrets.h` 时不会仅因缺少配置头文件中断 Verify，但设备按占位配置启动、无法
  联网，启动时会在串口打印一条 WARNING；修改本地配置后需要重新 Verify 与 Upload。

v0.2 已完成 Arduino IDE 编译、烧录，以及 Codex／智谱页面、BOOT 按键、断网、过期
状态、错误响应、恢复和中文布局的实机验证。

## 文档

- [路线图](ROADMAP.md)：当前进度、首版验收清单和后续服务商计划。

## 许可证

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
