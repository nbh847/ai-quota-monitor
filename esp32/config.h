#pragma once

// 配置读取顺序：本地 secrets.h 优先（真实配置，已在 .gitignore 中），
// 缺失时回落到下面的占位默认值。回退只为避免 Arduino IDE Verify 因缺少
// 本地配置头文件而直接中断；占位值不是凭据，也没有任何设备能靠它连上网，
// 此时启动会在串口打印一条 WARNING。整体 Verify 与 Upload 仍需人工完成。
// Arduino 构建器处理草图目录外的 config.h 时，嵌套 include 的相对基准
// 可能是 config.h 所在目录，也可能是草图目录；两种布局都要兼容。
#if __has_include("secrets.h")
#include "secrets.h"
#define CONFIG_SECRETS_PRESENT 1
#elif __has_include("../secrets.h")
#include "../secrets.h"
#define CONFIG_SECRETS_PRESENT 1
#else
#define CONFIG_SECRETS_PRESENT 0
#endif

#ifndef WIFI_SSID
#define WIFI_SSID "YOUR_WIFI_NAME"
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#endif
#ifndef QUOTA_AGENT_BASE_URL
#define QUOTA_AGENT_BASE_URL "http://YOUR_AGENT_IP:8767"
#endif
