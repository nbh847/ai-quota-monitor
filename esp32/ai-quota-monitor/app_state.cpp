#include "app_state.h"

#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>

namespace {

SemaphoreHandle_t stateLock;

// 设备当前状态。所有对外读写都必须持有 stateLock，UiTask 只在锁内拷贝。
// 每个服务商保存独立的快照与链路状态，切页和拉取期间互不串数据。
DisplayState state{};

bool appIsReady = false;

// BOOT 事件队列：只记录"按下过"这个事实，重复按下不会连续跳页。
constexpr unsigned kPageQueueLen = 2;
QueueHandle_t pageQueue;

uint8_t clampProviderIndex(uint8_t index) {
  return index < PROVIDER_COUNT ? index : 0;
}

}  // namespace

bool appInit() {
  stateLock = xSemaphoreCreateMutex();
  if (stateLock == NULL) return false;

  pageQueue = xQueueCreate(kPageQueueLen, sizeof(uint8_t));
  if (pageQueue == NULL) {
    vSemaphoreDelete(stateLock);
    stateLock = NULL;
    return false;
  }

  state.wifiConnecting = true;
  for (size_t i = 0; i < PROVIDER_COUNT; i++) {
    state.providers[i].link = LinkState::AgentDown;
  }
  state.providerIndex = 0;
  appIsReady = true;
  return true;
}

bool appReady() {
  return appIsReady;
}

void appSetWifiConnecting(bool connecting) {
  xSemaphoreTake(stateLock, portMAX_DELAY);
  state.wifiConnecting = connecting;
  xSemaphoreGive(stateLock);
}

void appCommitSnapshot(uint8_t providerIndex, const QuotaSnapshot& snapshot) {
  xSemaphoreTake(stateLock, portMAX_DELAY);
  const uint8_t index = clampProviderIndex(providerIndex);
  state.providers[index].snapshot = snapshot;
  state.providers[index].link = LinkState::Up;
  xSemaphoreGive(stateLock);
}

void appMarkAgentDown(uint8_t providerIndex) {
  xSemaphoreTake(stateLock, portMAX_DELAY);
  state.providers[clampProviderIndex(providerIndex)].link = LinkState::AgentDown;
  xSemaphoreGive(stateLock);
}

DisplayState appTakeState() {
  xSemaphoreTake(stateLock, portMAX_DELAY);
  DisplayState copy = state;
  xSemaphoreGive(stateLock);
  return copy;
}

uint8_t appProviderIndex() {
  xSemaphoreTake(stateLock, portMAX_DELAY);
  uint8_t index = state.providerIndex;
  xSemaphoreGive(stateLock);
  return index;
}

void appNextProvider() {
  xSemaphoreTake(stateLock, portMAX_DELAY);
  state.providerIndex = (state.providerIndex + 1) % PROVIDER_COUNT;
  xSemaphoreGive(stateLock);
}

bool appPostNextPage() {
  if (pageQueue == NULL) return false;
  const uint8_t event = 1;
  // 队列满时丢弃，避免按键事件堆积；调用方仅在成功时唤醒 UI，
  // 保证队列事件数与任务通知数一致。
  return xQueueSend(pageQueue, &event, 0) == pdTRUE;
}

bool appTakeNextPage() {
  if (pageQueue == NULL) return false;
  uint8_t event = 0;
  return xQueueReceive(pageQueue, &event, 0) == pdTRUE;
}

const char* appProviderId(uint8_t providerIndex) {
  return PROVIDERS[clampProviderIndex(providerIndex)].id;
}
