#pragma once

// 复制本文件为同目录下的 secrets.h 后填写真实配置；secrets.h 已在 .gitignore 中。
// 模板内只保留占位值，禁止写入真实 Wi-Fi 口令、真实内网地址或任何账号凭据。
//
// 没有 secrets.h 时，config.h 会回落为同样的占位值，Verify 不会仅因缺少配置头文件
// 直接中断，但设备无法连接 Wi-Fi 或数据服务，启动时会在串口打印 WARNING。

#define WIFI_SSID "YOUR_WIFI_NAME"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// PC 上运行 pc-agent/monitor.py 的地址；固件自己拼接 /api/v1/quotas/<id>。
// 下面是示意值，必须替换为你自己机器的局域网地址，不要把真实地址提回本模板。
#define QUOTA_AGENT_BASE_URL "http://YOUR_AGENT_IP:8767"
