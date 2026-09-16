#include "app_state.h"

#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>

namespace {

SemaphoreHandle_t stateLock;

// 设备当前状态。所有对外读写都必须持有 stateLock，UiTask 只在锁内拷贝。
DisplayState state{};

bool appIsReady = false;

// BOOT 事件队列：只记录"按下过"这个事实，重复按下不会连续跳页。
constexpr unsigned kPageQueueLen = 2;
QueueHandle_t pageQueue;

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

  state.link = LinkState::Connecting;
  state.providerIndex = 0;
  appIsReady = true;
  return true;
}

bool appReady() {
  return appIsReady;
}

void appSetLinkState(LinkState linkState) {
  xSemaphoreTake(stateLock, portMAX_DELAY);
  state.link = linkState;
  xSemaphoreGive(stateLock);
}

void appCommitSnapshot(const QuotaSnapshot& snapshot) {
  xSemaphoreTake(stateLock, portMAX_DELAY);
  state.snapshot = snapshot;
  state.link = LinkState::Up;
  xSemaphoreGive(stateLock);
}

void appMarkAgentDown() {
  xSemaphoreTake(stateLock, portMAX_DELAY);
  state.link = LinkState::AgentDown;
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
  // 循环取模：PROVIDER_COUNT 为 1 时索引保持为 0，按键不产生任何变化。
  state.providerIndex = (state.providerIndex + 1) % PROVIDER_COUNT;
  xSemaphoreGive(stateLock);
}

void appPostNextPage() {
  if (pageQueue == NULL) return;
  const uint8_t event = 1;
  xQueueSend(pageQueue, &event, 0);  // 队列满时丢弃，避免按键事件堆积
}

bool appTakeNextPage() {
  if (pageQueue == NULL) return false;
  uint8_t event = 0;
  return xQueueReceive(pageQueue, &event, 0) == pdTRUE;
}

const char* appProviderId() {
  uint8_t index = appProviderIndex();
  if (index >= PROVIDER_COUNT) index = 0;
  return PROVIDERS[index].id;
}
