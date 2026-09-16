#pragma once

#include <Arduino.h>

// 初始化 BOOT 按键输入引脚与初始电平采样。
void inputInit();

// 非阻塞按键读取：一次稳定按下只会返回一次 true，返回前调用方消费该事件。
bool inputWasPressed();
