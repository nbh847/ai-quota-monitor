#pragma once

#include <Arduino.h>

enum class InputButton : uint8_t {
  None,
  Boot,
  External,
};

// 初始化 BOOT 与 GPIO13 外接按键的输入引脚和初始电平采样。
void inputInit();

// 非阻塞按键读取：任一按键的一次稳定按下只返回一次对应来源，长按不重复触发。
InputButton inputPressed();
