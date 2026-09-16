# Repository Guidelines

## 项目定位

本项目是一个基于 ESP32-S3 + OLED 的 AI 服务商额度监控显示器。首版只验证 Codex
额度展示；后续通过独立服务商适配器增加智谱、商汤日日新、OpenRouter 等服务商。

当前状态：PC Agent 与 ESP32-S3 固件代码均已写完，PC 侧 41 项单元测试与本机 HTTP
冒烟验证通过；固件已在 Arduino IDE 中编译、烧录，并完成 Codex 双窗口、BOOT、断网、
过期状态、错误响应与恢复路径的实机验收。v0.1 已完成。

## 文档入口与状态纪律

- `README.md`：对外项目定位、首版范围和使用边界，只描述当前真实状态。
- `ROADMAP.md`：当前进度、待办、风险和验证记录。实现或验证改变状态后必须同步。
- `goals/`：施工文档，记录当前版本的需求、边界、数据模型和验收标准；开发期间纳入 Git，
  完成全部验收并将结果同步到 `ROADMAP.md` 后删除，Git 历史保留施工记录。

未实现、待确认或尚未实机验证的内容，必须明确标注对应状态，不得写成已支持或已通过。

## 实现边界

- 服务商接入应通过适配器和统一额度快照对接，显示层不绑定某一家服务商的字段。
- Codex、智谱、商汤日日新和 OpenRouter 的数据来源、接口字段和额度口径必须分别核对；
  不凭接口名称或记忆编造协议。
- 密码、Token、真实网络地址和本地账号信息不得写入仓库。使用本地配置时提供安全模板，
  并将真实配置加入忽略规则。
- ESP32 固件不应承担不必要的凭据管理；在数据来源未确认前，优先评估本机或局域网桥接
  服务方案。
- 网络请求、按键去抖和屏幕刷新优先采用基于 `millis()` 的非阻塞时序。

## Codex 登录红线

- Agent 禁止自行执行 `codex login`、`account/login/start`、`account/login/cancel`、
  `account/logout`，以及删除、覆盖或修改 `C:\Users\ronnie\.codex\auth.json` 等会创建、
  替换、刷新或失效 Codex 登录态的操作。
- 用户提出“修复登录”“再试试”“检查登录”等泛化要求，不视为本次登录操作的授权。
- 每次确需登录前，必须先说明具体命令或方法、影响的登录主体和凭据存储，以及是否可能
  覆盖、取消或使当前会话失效；只有得到用户针对该次操作的二次明确确认（例如“确认登录”）
  后才能执行。
- 未获得二次确认时，只允许执行不改变认证状态的只读检查，例如 `codex login status` 和
  `account/read`。登录失效时，PC Agent 应返回 `auth_required`，Agent 只能报告并请用户
  手动登录。

## 验证要求

- PC Agent 有 41 项单元测试：在 `pc-agent/` 下运行 `.venv/Scripts/python -m unittest discover -s
  tests -q`；同时运行 `.venv/Scripts/python -m py_compile monitor.py quotas.py codex_client.py`。
- 固件没有编译入口：本开发环境未安装 arduino-cli，Verify 与 Upload 由人工在 Arduino IDE
  中完成；必须在交付时说明开发板、草图以及串口或屏幕实机结果。本机已安装
  `xtensa-esp-elf-g++` 与 ESP32 Core，可复用 Core 的 flags 做只读 `-fsyntax-only`
  语法检查；该检查不链接、不生成固件，不能替代 Verify，记录结果时必须注明这一点。
- 至少验证数据成功、字段缺失、过期、请求失败、网络恢复和 BOOT 重复触发边界；固件侧
  这些路径已完成实机验收，后续相关改动必须执行对应回归验证。

## 语言与修改范围

- 文档、注释、提交描述和讨论使用中文；代码、命令、变量名和文件名使用英文。
- 只修改当前任务直接相关的文件，不顺手重构无关内容。
- 新增服务商或改变数据模型时，必须同步更新 `README.md`、`ROADMAP.md` 和当前 Goal
  文档中受影响的事实。
