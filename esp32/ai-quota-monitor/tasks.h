#pragma once

#include <Arduino.h>

// 创建并统一放行网络、显示与输入任务。任一任务创建失败时回滚已创建的任务
// 并返回 false，不留下部分运行状态。
bool startTasks();

// 串口输出堆余量与任务栈高水位，用于实机核对栈配置。
void reportDiagnostics();
