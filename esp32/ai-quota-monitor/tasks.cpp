#include "tasks.h"

#include <WiFi.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include "../config.h"

#include "app_state.h"
#include "input.h"
#include "quota_net.h"
#include "ui.h"

// 时序与资源常量。10000ms 拉取间隔与 1000ms 本地刷新是首版冻结值；
// 失败退避 30s，避免 Agent 下线时形成密集重试。
const unsigned long FETCH_INTERVAL_MS = 10000;
const unsigned long FETCH_BACKOFF_MS = 30000;
const unsigned long WIFI_CHECK_MS = 1000;
const unsigned long WIFI_RETRY_BEGIN_MS = 10000;
const unsigned long SLEEP_MIN_MS = 10;      // 调度等待下限，防止忙等
const unsigned long UI_REFRESH_MS = 1000;   // 页脚时钟本地刷新，不触发网络
const unsigned long INPUT_POLL_MS = 5;      // 远小于 20ms 去抖窗口

const unsigned NET_TASK_STACK = 10240;
const unsigned UI_TASK_STACK = 10240;
const unsigned INPUT_TASK_STACK = 3072;
const unsigned NET_TASK_PRIO = 2;
const unsigned UI_TASK_PRIO = 2;
const unsigned INPUT_TASK_PRIO = 1;

// 句柄供 reportDiagnostics 读取栈高水位；未创建成功时为 NULL。
static TaskHandle_t networkTaskHandle = NULL;
static TaskHandle_t uiTaskHandle = NULL;
static TaskHandle_t inputTaskHandle = NULL;

// 新任务先阻塞在各自的任务通知上。三个任务全部创建成功后才统一放行，
// 避免部分创建失败时系统已经进入不完整的业务运行状态。
static void waitForTaskStart() {
  ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
}

static void deleteCreatedTask(TaskHandle_t& handle) {
  if (handle == NULL) return;
  vTaskDelete(handle);
  handle = NULL;
}

static void rollbackCreatedTasks() {
  // 任务此时仍阻塞在启动通知上，可以安全删除，不会持有业务 Mutex 或操作硬件。
  deleteCreatedTask(inputTaskHandle);
  deleteCreatedTask(uiTaskHandle);
  deleteCreatedTask(networkTaskHandle);
}

static void releaseCreatedTasks() {
  // 先放行显示消费者，再放行输入与网络生产者。
  xTaskNotifyGive(uiTaskHandle);
  xTaskNotifyGive(inputTaskHandle);
  xTaskNotifyGive(networkTaskHandle);
}

static bool createTask(void (*taskFn)(void*), const char* name, unsigned stackSize,
                       unsigned priority, int core, TaskHandle_t& handle) {
  if (xTaskCreatePinnedToCore(taskFn, name, stackSize, NULL, priority, &handle, core) != pdPASS) {
    Serial.printf("FATAL: %s create failed\n", name);
    handle = NULL;
    rollbackCreatedTasks();
    return false;
  }
  return true;
}

// millis() 回绕安全：把截止时间当作可比较的 32 位有符号差值，
// 跨越 49.7 天回绕时判断结果仍然正确。
static bool isDue(unsigned long due, unsigned long now) {
  return (long)(now - due) >= 0;
}

static unsigned long msUntil(unsigned long due, unsigned long now) {
  const long left = (long)(due - now);
  return left > 0 ? (unsigned long)left : 0;
}

// NetworkTask（Core 0）：Wi-Fi 状态机与数据拉取的唯一所有者。
// 服务商索引在请求开始时锁定：成功提交到该页快照，失败只标记该页，
// 旧页的迟到响应不会覆盖新页。切页后立即补拉一次新页数据。
static void networkTask(void*) {
  waitForTaskStart();

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  appSetWifiConnecting(true);

  bool wifiWasConnected = false;
  bool agentWasUp = false;
  int retryBeginLeft = WIFI_RETRY_BEGIN_MS / WIFI_CHECK_MS;
  unsigned long fetchDue = 0;
  uint8_t lastPageIndex = PROVIDER_COUNT;  // 无效初值：首轮必然按切页处理

  while (true) {
    if (WiFi.status() != WL_CONNECTED) {
      if (wifiWasConnected) {
        wifiWasConnected = false;
        // 运行时断线：各页最近有效快照继续留在屏幕上。
        appSetWifiConnecting(true);
        agentWasUp = false;
        Serial.println("WiFi disconnected");
      }
      // ESP32 内部重试耗尽后会停在未连接状态，这里按受控间隔重启连接流程。
      if (--retryBeginLeft <= 0) {
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
        retryBeginLeft = WIFI_RETRY_BEGIN_MS / WIFI_CHECK_MS;
      }
      vTaskDelay(WIFI_CHECK_MS / portTICK_PERIOD_MS);
      continue;
    }

    if (!wifiWasConnected) {
      wifiWasConnected = true;
      retryBeginLeft = WIFI_RETRY_BEGIN_MS / WIFI_CHECK_MS;
      appSetWifiConnecting(false);
      Serial.print("ESP32 IP: ");
      Serial.println(WiFi.localIP());
      fetchDue = millis();  // 首次上线或恢复后立刻补取一次
    }

    const uint8_t pageIndex = appProviderIndex();
    if (pageIndex != lastPageIndex) {
      lastPageIndex = pageIndex;
      fetchDue = millis();  // 切页后立即拉取新页数据
    }

    const unsigned long now = millis();
    if (!isDue(fetchDue, now)) {
      // 未到期时睡到截止，上限保证断线检测不被拖慢，下限防忙等。
      unsigned long waitMs = msUntil(fetchDue, now);
      if (waitMs > WIFI_CHECK_MS) waitMs = WIFI_CHECK_MS;
      if (waitMs < SLEEP_MIN_MS) waitMs = SLEEP_MIN_MS;
      vTaskDelay(waitMs / portTICK_PERIOD_MS);
      continue;
    }

    QuotaSnapshot snapshot{};
    const bool ok = netFetchOnce(pageIndex, snapshot);
    if (ok) {
      appCommitSnapshot(pageIndex, snapshot);
      if (!agentWasUp) Serial.println("Agent connected");
      agentWasUp = true;
    } else {
      appMarkAgentDown(pageIndex);
      if (agentWasUp) Serial.println("Agent unavailable");
      agentWasUp = false;
    }
    fetchDue = millis() + (ok ? FETCH_INTERVAL_MS : FETCH_BACKOFF_MS);
  }
}

// UiTask（Core 1）：运行时唯一允许执行 OLED 绘制和 sendBuffer 的任务。
// 锁内复制完整快照，绘制在锁外进行；BOOT 事件在这里消费并切换服务商。
// 每帧最多消费一次按键事件，避免连按时跳页。
static void uiTask(void*) {
  waitForTaskStart();

  while (true) {
    if (appTakeNextPage()) {
      const uint8_t before = appProviderIndex();
      appNextProvider();
      const uint8_t after = appProviderIndex();
      // 切页后立即触发新页拉取由 NetworkTask 检测索引变化完成；
      // 这里打印事件便于实机核对"一次按下只触发一次"。
      Serial.printf("BOOT event: provider %u -> %u (%s)\n", (unsigned)before,
                    (unsigned)after, appProviderId(after));
    }

    uiDraw(appTakeState());
    vTaskDelay(UI_REFRESH_MS / portTICK_PERIOD_MS);
  }
}

// InputTask（Core 1）：只读取去抖后的按键电平并发送页面切换事件。
static void inputTask(void*) {
  waitForTaskStart();

  while (true) {
    if (inputWasPressed()) appPostNextPage();
    vTaskDelay(INPUT_POLL_MS / portTICK_PERIOD_MS);
  }
}

bool startTasks() {
  if (!createTask(networkTask, "net", NET_TASK_STACK, NET_TASK_PRIO, 0, networkTaskHandle)) {
    return false;
  }
  if (!createTask(uiTask, "ui", UI_TASK_STACK, UI_TASK_PRIO, 1, uiTaskHandle)) {
    return false;
  }
  if (!createTask(inputTask, "in", INPUT_TASK_STACK, INPUT_TASK_PRIO, 1, inputTaskHandle)) {
    return false;
  }
  releaseCreatedTasks();
  return true;
}

static unsigned stackHigh(TaskHandle_t handle) {
  return handle == NULL ? 0 : uxTaskGetStackHighWaterMark(handle);
}

void reportDiagnostics() {
  DisplayState state = appTakeState();
  const uint8_t index = state.providerIndex % PROVIDER_COUNT;
  const ProviderState& current = state.providers[index];
  const char* link = "OFF";
  if (state.wifiConnecting) link = "WIFI";
  if (current.link == LinkState::Up) link = "UP";

  Serial.printf("diag heap=%uKB net=%uB ui=%uB in=%uB page=%u(%s) link=%s win=%u sync=%s\n",
                (unsigned)(ESP.getFreeHeap() / 1024),
                stackHigh(networkTaskHandle), stackHigh(uiTaskHandle),
                stackHigh(inputTaskHandle), (unsigned)index,
                PROVIDERS[index].id, link, current.snapshot.windowCount,
                current.snapshot.syncLabel[0] != '\0' ? current.snapshot.syncLabel : "--:--");
}
