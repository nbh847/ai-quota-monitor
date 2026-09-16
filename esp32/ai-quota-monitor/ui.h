#pragma once

#include "app_state.h"

// 整帧重绘唯一页面：页首（服务商 / 套餐 / 状态）、5H 与 7D 双窗口
// （剩余比例 + 连续矩形进度条 + 重置时间）、SYNC / STALE 页脚。
// state 是 UiTask 在 Mutex 内复制出的快照，绘制过程不持锁。
void uiDraw(const DisplayState& state);

// 任务启动前的启动画面：唯一一次非 UiTask 绘制，避免屏幕长时间空白。
void uiDrawBoot();
