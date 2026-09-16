#pragma once

#include <Arduino.h>

#include "models.h"

// 拉取指定服务商的额度快照：只读取 PC Agent 已归一化的白名单字段。
// 服务商索引在请求开始时锁定，旧页响应只会提交回旧页，不会覆盖新页。
// 成功时 out 被整体替换；失败时输出不改动，调用方保留上次有效快照
// 继续显示。响应体不外传，也不写入串口日志。
bool netFetchOnce(uint8_t providerIndex, QuotaSnapshot& out);
