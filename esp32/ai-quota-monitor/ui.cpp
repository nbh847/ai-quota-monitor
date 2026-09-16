#include "ui.h"

#include <esp_timer.h>
#include <string.h>
#include <U8g2lib.h>

#include "models.h"

extern U8G2_SH1106_128X64_NONAME_F_HW_I2C oled;

namespace {

// 版面坐标：128x64，页首与分隔线固定，两个窗口等高排列，页脚贴底。
const int MARGIN_X = 2;
const int RIGHT_EDGE = 126;
const int PLAN_X = 44;
const int HEADER_BASELINE = 10;
const int DIVIDER_Y = 12;
const int BAR_X = 40;
const int BAR_W = 86;
const int BAR_H = 9;
const int BAR1_Y = 15;
const int BAR2_Y = 35;
const int LABEL1_BASELINE = 22;
const int LABEL2_BASELINE = 42;
const int RESET1_BASELINE = 32;
const int RESET2_BASELINE = 52;
const int FOOTER_BASELINE = 62;

const int LOW_QUOTA_PERCENT = 20;  // 低于该值反白显示，不闪烁
const int STALE_AFTER_SEC = 180;   // 3 分钟无成功更新即视为过期

// 右对齐绘制：rightX 是文字右边界。
void drawStrRight(const char* text, int rightX, int y) {
  oled.drawStr(rightX - oled.getStrWidth(text) + 1, y, text);
}

// 页首状态：设备侧连接状态优先于 Agent 报告的业务状态。
const char* statusLabel(const DisplayState& state) {
  if (state.link == LinkState::Connecting) return "WIFI";
  if (state.link == LinkState::AgentDown) return "OFF";

  const char* status = state.snapshot.status;
  if (strcmp(status, "ok") == 0) return "OK";
  if (strcmp(status, "auth_required") == 0) return "LOGIN";
  if (strcmp(status, "invalid_data") == 0) return "BAD";
  if (strcmp(status, "stale") == 0) return "STALE";
  // Agent 可达但取不到数据源，与"设备连不上 Agent"的 OFF 区分开。
  if (strcmp(status, "unavailable") == 0) return "SRC";
  return "OFF";
}

// 页首显示统一大写，避免小写字母在 128px 内显得杂乱。
void upperCopy(char* dest, size_t capacity, const char* src) {
  size_t n = 0;
  while (n + 1 < capacity && src != nullptr && src[n] != '\0') {
    char c = src[n];
    if (c >= 'a' && c <= 'z') c -= 32;
    dest[n] = c;
    n++;
  }
  dest[n] = '\0';
}

// 连续矩形进度条：先画外框再画填充，按剩余比例从左向右填充。
void drawBar(int y, int16_t percent) {
  oled.drawFrame(BAR_X, y, BAR_W, BAR_H);
  const int fillW = (int)((BAR_W - 2) * constrain(percent, 0, 100) / 100.0);
  if (fillW > 0) oled.drawBox(BAR_X + 1, y + 1, fillW, BAR_H - 2);
}

// 低于阈值时把剩余比例反白显示，保持静态，不做闪烁告警。
void drawPercent(const char* text, int x, int y, int16_t percent) {
  if (percent < LOW_QUOTA_PERCENT) {
    const int w = oled.getStrWidth(text);
    oled.setDrawColor(1);
    oled.drawBox(x - 1, y - 7, w + 2, 9);
    oled.setDrawColor(0);
    oled.drawStr(x, y, text);
    oled.setDrawColor(1);
    return;
  }
  oled.drawStr(x, y, text);
}

void drawWindow(const QuotaWindow& win, int barY, int labelY, int resetY) {
  char line[16];
  snprintf(line, sizeof(line), "%s %d%%", win.label, win.remainingPercent);
  drawPercent(line, MARGIN_X, labelY, win.remainingPercent);

  drawBar(barY, win.remainingPercent);

  oled.drawStr(MARGIN_X, resetY, "R");
  drawStrRight(win.resetLabel, RIGHT_EDGE, resetY);
}

// 页脚：数据新鲜时显示 SYNC HH:MM；过期后保留旧数据并显示 STALE Nm。
void drawFooter(const DisplayState& state) {
  int64_t staleSec = -1;
  const QuotaSnapshot& snap = state.snapshot;

  if (strcmp(snap.status, "stale") == 0) {
    // 本机每 10s 轮询会不断取到新响应，陈旧判断优先采信 Agent 报告的快照年龄。
    staleSec = snap.ageSec > 0 ? (int64_t)snap.ageSec : STALE_AFTER_SEC;
  } else if (snap.fetchedAtUs > 0) {
    staleSec = (esp_timer_get_time() - snap.fetchedAtUs) / 1000000;
  }

  if (staleSec >= STALE_AFTER_SEC) {
    oled.drawStr(MARGIN_X, FOOTER_BASELINE, "STALE");
    char line[8];
    snprintf(line, sizeof(line), "%lldm", (long long)(staleSec / 60));
    drawStrRight(line, RIGHT_EDGE, FOOTER_BASELINE);
    return;
  }

  oled.drawStr(MARGIN_X, FOOTER_BASELINE, "SYNC");
  drawStrRight(snap.syncLabel[0] != '\0' ? snap.syncLabel : "--:--",
               RIGHT_EDGE, FOOTER_BASELINE);
}

}  // namespace

void uiDraw(const DisplayState& state) {
  oled.clearBuffer();
  oled.setDrawColor(1);

  const uint8_t index = state.providerIndex % PROVIDER_COUNT;
  const QuotaSnapshot& snap = state.snapshot;

  oled.setFont(u8g2_font_6x10_tf);
  char name[16];
  upperCopy(name, sizeof(name), PROVIDERS[index].displayName);
  oled.drawStr(MARGIN_X, HEADER_BASELINE, name);

  char plan[16];
  upperCopy(plan, sizeof(plan), snap.plan[0] != '\0' ? snap.plan : "--");
  oled.drawStr(PLAN_X, HEADER_BASELINE, plan);

  drawStrRight(statusLabel(state), RIGHT_EDGE, HEADER_BASELINE);
  oled.drawLine(MARGIN_X, DIVIDER_Y, RIGHT_EDGE, DIVIDER_Y);

  oled.setFont(u8g2_font_5x8_tf);
  if (snap.windowCount == 0) {
    oled.drawStr(MARGIN_X, LABEL1_BASELINE, "NO DATA");
  }
  for (uint8_t i = 0; i < snap.windowCount && i < MAX_WINDOWS; i++) {
    const int barY = (i == 0) ? BAR1_Y : BAR2_Y;
    const int labelY = (i == 0) ? LABEL1_BASELINE : LABEL2_BASELINE;
    const int resetY = (i == 0) ? RESET1_BASELINE : RESET2_BASELINE;
    drawWindow(snap.windows[i], barY, labelY, resetY);
  }

  drawFooter(state);
  oled.sendBuffer();
}

void uiDrawBoot() {
  oled.clearBuffer();
  oled.setDrawColor(1);
  oled.setFont(u8g2_font_6x10_tf);
  oled.drawStr(MARGIN_X, 20, "Quota Monitor");
  oled.setFont(u8g2_font_5x8_tf);
  oled.drawStr(MARGIN_X, 34, "Starting...");
  oled.sendBuffer();
}
