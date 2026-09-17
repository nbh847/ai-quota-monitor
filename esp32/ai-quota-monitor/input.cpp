#include "input.h"

namespace {

constexpr int kButtonPin = 0;        // BOOT 按键，INPUT_PULLUP 上拉，按下为低电平
constexpr unsigned long kDebounceMs = 20;

unsigned long rawChangedAtMs = 0;
unsigned lastRaw = HIGH;            // 最近一次读取的原始电平
unsigned stableRaw = HIGH;          // 已通过持续时间确认的稳定电平

}  // namespace

void inputInit() {
  pinMode(kButtonPin, INPUT_PULLUP);
  lastRaw = digitalRead(kButtonPin);
  stableRaw = lastRaw;
  rawChangedAtMs = millis();
}

bool inputWasPressed() {
  const unsigned long now = millis();
  const unsigned raw = digitalRead(kButtonPin);
  if (raw != lastRaw) {
    lastRaw = raw;
    rawChangedAtMs = now;
    return false;
  }

  // 原始电平连续稳定满去抖窗口后才提交变化。只在稳定的下降沿产生事件，
  // 长按不会重复触发；稳定释放后才能识别下一次按下。
  if (raw != stableRaw && now - rawChangedAtMs >= kDebounceMs) {
    stableRaw = raw;
    return stableRaw == LOW;
  }
  return false;
}
