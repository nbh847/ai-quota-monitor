#pragma once

#include <Arduino.h>

// 服务商条目：BOOT 按键按列表顺序循环切换。
// v0.2 固定 Codex -> Zhipu；新增服务商只追加条目并同步 PROVIDER_COUNT。
struct ProviderEntry {
  const char* id;          // 与 PC Agent 的 provider_id 一致，拼进请求路径
  const char* displayName; // 页首标题；cjkTitle 为 true 时是 UTF-8 中文
  bool cjkTitle;           // 页首标题需要中文字体绘制
};

constexpr size_t PROVIDER_COUNT = 2;
constexpr const ProviderEntry PROVIDERS[PROVIDER_COUNT] = {
  {"codex", "Codex", false},
  {"zhipu", "智谱", true},
};

// 单个额度窗口。PC Agent 已完成归一化：比例已 clamp 到 0..100，
// resetLabel 是 PC 端格式化的本地时间 "MM-DD HH:MM"，固件不再解析 epoch。
struct QuotaWindow {
  char label[8];      // "5H" / "7D"，最多保留 7 个字符 + 结尾 \0
  char resetLabel[16]; // "09-15 17:52"，最多保留 15 个字符 + 结尾 \0
  int16_t remainingPercent; // 0..100
};

// PC Agent 一次响应最多返回 2 个窗口（primary / secondary）。
constexpr size_t MAX_WINDOWS = 2;

// 额度快照：一次成功请求的完整结果，成功时整体原子替换。
struct QuotaSnapshot {
  char plan[12];       // "plus" 等，最多保留 11 个字符 + 结尾 \0
  char status[16];     // ok / auth_required / unavailable / invalid_data / stale
  char syncLabel[8];   // Agent 格式化的最近成功同步时间 "HH:MM"
  QuotaWindow windows[MAX_WINDOWS];
  uint8_t windowCount;
  uint32_t ageSec;     // Agent 报告的快照年龄（秒），0 表示本次响应未提供
  int64_t fetchedAtUs; // 成功时刻的 esp_timer_get_time()，用于计算陈旧分钟数
  bool hasData;        // windowCount > 0
};

// 有界字符串拷贝：目标缓冲区末尾永远保留 \0，拼接不越界、不产生半个字符串。
inline void copyBounded(const char* src, char* dest, size_t capacity) {
  size_t n = 0;
  if (src != nullptr) {
    while (n + 1 < capacity && src[n] != '\0') {
      dest[n] = src[n];
      n++;
    }
  }
  dest[n] = '\0';
}
