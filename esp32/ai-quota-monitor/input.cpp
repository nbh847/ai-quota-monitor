#include "input.h"

namespace {

constexpr uint8_t kBootButtonPin = 0;      // BOOT 按键，按下为低电平
constexpr uint8_t kExternalButtonPin = 13; // 外接按键 OUT，按下输出高电平
constexpr unsigned long kDebounceMs = 20;

struct ButtonState {
  uint8_t pin;
  uint8_t pressedLevel;
  unsigned long rawChangedAtMs;
  unsigned lastRaw;
  unsigned stableRaw;
};

ButtonState bootButton{kBootButtonPin, LOW, 0, HIGH, HIGH};
ButtonState externalButton{kExternalButtonPin, HIGH, 0, LOW, LOW};

void initButton(ButtonState& button, uint8_t mode) {
  pinMode(button.pin, mode);
  button.lastRaw = digitalRead(button.pin);
  button.stableRaw = button.lastRaw;
  button.rawChangedAtMs = millis();
}

bool wasPressed(ButtonState& button, unsigned long now) {
  const unsigned raw = digitalRead(button.pin);
  if (raw != button.lastRaw) {
    button.lastRaw = raw;
    button.rawChangedAtMs = now;
    return false;
  }

  // 原始电平连续稳定满去抖窗口后才提交变化。只在稳定的按下沿产生事件，
  // 长按不会重复触发；稳定释放后才能识别下一次按下。
  if (raw != button.stableRaw && now - button.rawChangedAtMs >= kDebounceMs) {
    button.stableRaw = raw;
    return button.stableRaw == button.pressedLevel;
  }
  return false;
}

}  // namespace

void inputInit() {
  initButton(bootButton, INPUT_PULLUP);
  initButton(externalButton, INPUT_PULLDOWN);
}

InputButton inputPressed() {
  const unsigned long now = millis();
  const bool bootPressed = wasPressed(bootButton, now);
  const bool externalPressed = wasPressed(externalButton, now);
  if (bootPressed) return InputButton::Boot;
  if (externalPressed) return InputButton::External;
  return InputButton::None;
}
