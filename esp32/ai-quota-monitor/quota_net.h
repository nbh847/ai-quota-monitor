#pragma once

#include <Arduino.h>

#include "models.h"

// 拉取当前页服务商的额度快照：只读取 PC Agent 已归一化的白名单字段。
// 成功时 out 被整体替换。失败时输出不改动，调用方保留上次有效快照
// 继续显示。响应体不外传，也不写入串口日志。
bool netFetchOnce(QuotaSnapshot& out);
