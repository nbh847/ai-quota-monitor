#pragma once

#include <Arduino.h>

#include "models.h"

// 设备侧链路状态。Agent 报告的 ok/stale 等业务状态放在 QuotaSnapshot::status；
// 这里只表达"能不能取到数据"。Wi-Fi 层用全局 wifiConnecting 表达；
// Agent 可达性按服务商独立记录，切页时互不影响。
enum class LinkState : uint8_t {
  Up,          // 最近一次该服务商的 HTTP 成功
  AgentDown,   // 最近一次该服务商的 HTTP 失败或数据无法解析
};

// 单个服务商的显示状态：独立快照 + 独立链路状态。
struct ProviderState {
  LinkState link;
  QuotaSnapshot snapshot;
};

// 显示状态快照：UiTask 在锁内整体拷贝，锁外绘制。
struct DisplayState {
  bool wifiConnecting;
  ProviderState providers[PROVIDER_COUNT];
  uint8_t providerIndex;
};

bool appInit();
bool appReady();

// Wi-Fi 层状态：未连接或刚上线时为 true，所有页面共用。
void appSetWifiConnecting(bool connecting);

// 某服务商请求成功：整体替换该页快照并置该页链路在线。
void appCommitSnapshot(uint8_t providerIndex, const QuotaSnapshot& snapshot);
// 某服务商请求失败：只清该页链路位，保留该页最近一次有效快照。
void appMarkAgentDown(uint8_t providerIndex);

DisplayState appTakeState();

uint8_t appProviderIndex();
// BOOT 切换到下一页：按服务商列表循环，每次按下只前进一页。
void appNextProvider();
void appPostNextPage(); // BOOT 事件入队，只记一次
bool appTakeNextPage(); // UI 消费一次页面切换事件

// 指定页服务商 ID；索引越界时回落到第 0 项。
const char* appProviderId(uint8_t providerIndex);
