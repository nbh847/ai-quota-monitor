#include "quota_net.h"

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <esp_timer.h>
#include "../config.h"

#include "models.h"

namespace {

const int HTTP_CONNECT_TIMEOUT_MS = 1000;
const int HTTP_TIMEOUT_MS = 4000;

// 响应上限：PC Agent 的正常响应是几百字节，超限说明拿到的不是预期负载。
const size_t MAX_RESPONSE_BYTES = 8192;

// 拉取一个端点的响应体。所有分支都调用 http.end()，不在栈上残留连接。
bool httpGet(const char* endpoint, String& body) {
  HTTPClient http;
  http.setConnectTimeout(HTTP_CONNECT_TIMEOUT_MS);
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.begin(endpoint);

  const int code = http.GET();
  if (code != HTTP_CODE_OK) {
    http.end();
    return false;
  }

  body = http.getString();
  http.end();
  return body.length() > 0;
}

// 字段白名单：status / plan / updated_at_local / age_sec 与
// windows[].label / remaining_percent / reset_at_local。
// 其余字段一律不解析；窗口字段不全时只跳过该窗口，不提交半截数据。
bool parseQuota(const String& body, QuotaSnapshot& out) {
  JsonDocument doc;
  if (deserializeJson(doc, body)) return false;

  const JsonVariant statusVar = doc["status"];
  if (!statusVar.is<const char*>()) return false;

  QuotaSnapshot snapshot{};
  copyBounded(statusVar.as<const char*>(), snapshot.status, sizeof(snapshot.status));

  const JsonVariant planVar = doc["plan"];
  if (planVar.is<const char*>()) {
    copyBounded(planVar.as<const char*>(), snapshot.plan, sizeof(snapshot.plan));
  } else {
    copyBounded("--", snapshot.plan, sizeof(snapshot.plan));
  }

  const JsonVariant syncVar = doc["updated_at_local"];
  if (syncVar.is<const char*>()) {
    copyBounded(syncVar.as<const char*>(), snapshot.syncLabel,
                sizeof(snapshot.syncLabel));
  } else {
    copyBounded("--:--", snapshot.syncLabel, sizeof(snapshot.syncLabel));
  }

  const JsonVariant ageVar = doc["age_sec"];
  if (ageVar.is<double>()) {
    const int64_t age = static_cast<int64_t>(ageVar.as<double>());
    snapshot.ageSec = static_cast<uint32_t>(constrain(age, 0, 86400));
  }

  const JsonArray windows = doc["windows"].as<JsonArray>();
  if (!windows.isNull()) {
    for (const JsonVariant entry : windows) {
      if (snapshot.windowCount >= MAX_WINDOWS) break;

      const JsonObject obj = entry.as<JsonObject>();
      if (obj.isNull()) continue;

      const JsonVariant labelVar = obj["label"];
      const JsonVariant pctVar = obj["remaining_percent"];
      if (!labelVar.is<const char*>() || !pctVar.is<double>()) continue;

      QuotaWindow& win = snapshot.windows[snapshot.windowCount];
      copyBounded(labelVar.as<const char*>(), win.label, sizeof(win.label));
      // Agent 已归一化，这里再夹一次，保证显示层不用处理越界值。
      win.remainingPercent =
          static_cast<int16_t>(constrain(pctVar.as<double>(), 0.0, 100.0));

      const JsonVariant resetVar = obj["reset_at_local"];
      if (resetVar.is<const char*>()) {
        copyBounded(resetVar.as<const char*>(), win.resetLabel, sizeof(win.resetLabel));
      } else {
        copyBounded("--:--", win.resetLabel, sizeof(win.resetLabel));
      }
      snapshot.windowCount++;
    }
  }

  snapshot.hasData = snapshot.windowCount > 0;
  out = snapshot;
  return true;
}

}  // namespace

bool netFetchOnce(uint8_t providerIndex, QuotaSnapshot& out) {
  if (providerIndex >= PROVIDER_COUNT) return false;
  const char* providerId = PROVIDERS[providerIndex].id;
  if (providerId == nullptr) return false;

  String endpoint = QUOTA_AGENT_BASE_URL "/api/v1/quotas/";
  endpoint += providerId;

  String body;
  if (!httpGet(endpoint.c_str(), body)) return false;
  if (static_cast<size_t>(body.length()) > MAX_RESPONSE_BYTES) return false;

  if (!parseQuota(body, out)) return false;

  // 校验通过的时刻才算成功，用于设备侧计算陈旧分钟数。
  out.fetchedAtUs = esp_timer_get_time();
  return true;
}
