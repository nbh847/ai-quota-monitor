#include "input.h"

namespace {

constexpr int kButtonPin = 0;        // BOOT 按键，INPUT_PULLUP 上拉，按下为低电平
constexpr unsigned long kDebounceMs = 20;

unsigned long lastSampleMs = 0;
unsigned lastRaw = 0;                // 上一次采样值，用于判断电平是否稳定
bool stableLow = false;             // 当前稳定电平
bool pressPending = false;          // 已确认按下但事件尚未被消费

}  // namespace

void inputInit() {
  pinMode(kButtonPin, INPUT_PULLUP);
  lastRaw = digitalRead(kButtonPin);
  stableLow = (lastRaw == LOW);
  lastSampleMs = millis();
}

bool inputWasPressed() {
  const unsigned long now = millis();
  if (now - lastSampleMs < kDebounceMs) return false;
  lastSampleMs = now;

  const unsigned raw = digitalRead(kButtonPin);
  if (raw == lastRaw) {
    // 连续两次采样电平相同才视为稳定变化，抖动期间的单次跳变不产生事件。
    const bool low = (raw == LOW);
    if (low && !stableLow) pressPending = true;
    stableLow = low;
  }
  lastRaw = raw;

  const bool pressed = pressPending;
  pressPending = false;
  return pressed;
}
