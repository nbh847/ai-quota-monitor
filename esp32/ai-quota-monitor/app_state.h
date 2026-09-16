#pragma once

#include <Arduino.h>

#include "models.h"

// 设备侧连接状态。Agent 报告的 ok/stale 等业务状态放在 QuotaSnapshot::status；
// 这里只表达"能不能取到数据"，由 UI 层优先展示设备侧状态。
enum class LinkState : uint8_t {
  Connecting,  // Wi-Fi 未连接或刚上线
  Up,          // 最近一次 HTTP 成功
  AgentDown,   // Wi-Fi 已连但 Agent 不可达或返回无法解析的数据
};

// 显示状态快照：UiTask 在锁内整体拷贝，锁外绘制。
struct DisplayState {
  LinkState link;
  QuotaSnapshot snapshot;
  uint8_t providerIndex;
};

bool appInit();
bool appReady();

void appSetLinkState(LinkState state);
// 成功请求：整体替换快照并置 Agent 在线。
void appCommitSnapshot(const QuotaSnapshot& snapshot);
// 请求失败：只清 Agent 位，保留最近一次有效快照供继续显示。
void appMarkAgentDown();

DisplayState appTakeState();

uint8_t appProviderIndex();
// BOOT 切换到下一页：按服务商列表循环，列表长度为 1 时索引保持不变。
void appNextProvider();
void appPostNextPage(); // BOOT 事件入队，只记一次
bool appTakeNextPage(); // UI 消费一次页面切换事件

// 当前页服务商 ID；索引越界时回落到第 0 项。
const char* appProviderId();
