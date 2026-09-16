#include <Wire.h>
#include <U8g2lib.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "app_state.h"
#include "input.h"
#include "tasks.h"
#include "ui.h"

#include "../config.h"

#define SDA_PIN 8
#define SCL_PIN 9

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

const unsigned long DIAG_INTERVAL_MS = 60000;

// 主循环只负责低频诊断输出与让出 CPU，不调度输入、UI 或网络。
// 业务调度全部在 NetworkTask / UiTask / InputTask 内完成。
unsigned long lastDiag = 0;

// 同步原语或任务创建失败后的停机：串口连续提示 30 秒并让出 CPU，便于读取日志。
// 不调用 reportDiagnostics，因为此时可能已有句柄为空或尚未创建。
// startTasks 失败前会删除全部已创建且尚未放行的任务，不留下部分运行状态。
void safetyHalt() {
  for (int i = 0; i < 30; i++) {
    Serial.println("FATAL HALT: system not ready, check the log above");
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
  vTaskDelay(portMAX_DELAY);
}

void setup() {
  Serial.begin(115200);
  Serial.println("AI Quota Monitor v0.2");
#if !CONFIG_SECRETS_PRESENT
  Serial.println("WARNING: esp32/secrets.h missing, using placeholder config; copy esp32/secrets.example.h to esp32/secrets.h and fill in real values");
#endif

  Wire.begin(SDA_PIN, SCL_PIN);
  oled.begin();
  inputInit();

  // 中文字形自检：v0.2 智谱页标题依赖文泉驿字体的「智」「谱」两字形。
  // 缺字时标题会显示为空白，这里在串口给出可核对的证据。
  oled.setFont(u8g2_font_wqy12_t_gb2312a);
  const int glyphZhi = u8g2_GetGlyphWidth(oled.getU8g2(), 0x667A);
  const int glyphPu = u8g2_GetGlyphWidth(oled.getU8g2(), 0x8C31);
  oled.setFont(u8g2_font_6x10_tf);
  Serial.printf("CJK glyph check: zhi=%d pu=%d\n", glyphZhi, glyphPu);
  if (glyphZhi <= 0 || glyphPu <= 0) {
    Serial.println("WARNING: CJK glyph missing, zhipu title will be blank");
  }

  // 初始化期的唯一一次非 UiTask 绘制：任务启动前给出可见反馈，避免屏幕空白。
  uiDrawBoot();

  if (!appInit()) {
    safetyHalt();
    return;
  }

  if (!startTasks()) {
    safetyHalt();
    return;
  }

  Serial.println("Tasks started");
}

void loop() {
  const unsigned long now = millis();
  if (now - lastDiag >= DIAG_INTERVAL_MS) {
    lastDiag = now;
    // 验收期诊断输出，不参与任何业务调度；验收通过后应保留或按需移除。
    reportDiagnostics();
  }
  vTaskDelay(pdMS_TO_TICKS(1000));
}
