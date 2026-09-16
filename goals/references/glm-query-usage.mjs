#!/usr/bin/env node

/**
 * v0.2 智谱接入的只读参考代码快照。
 *
 * 来源：~/.agents/skills/glm-stats/scripts/query-usage.mjs
 * 快照时间：2026-09-16
 *
 * 本文件仅用于核对配置发现、请求端点、认证头和 unit 映射，不是项目运行入口。
 * 生产实现必须使用 pc-agent 下的原生 Python 代码，不得依赖 Node.js 或本文件。
 */

import https from 'https';
import fs from 'fs';
import path from 'path';

// Helper: auto-detect credentials from multiple sources
// Priority: models.json (real endpoints) > environment variables
function loadCredentialsFromSettings() {
  // 1. OpenClaw models.json (look for zhipu/z.ai/bigmodel provider)
  const modelsPath = path.join(process.env.HOME, '.qclaw', 'agents', 'main', 'agent', 'models.json');
  if (fs.existsSync(modelsPath)) {
    try {
      const raw = JSON.parse(fs.readFileSync(modelsPath, 'utf8'));
      const providers = raw.providers || {};
      for (const [, p] of Object.entries(providers)) {
        const url = (p.baseUrl || '').toLowerCase();
        if (url.includes('bigmodel.cn') || url.includes('z.ai')) {
          if (p.baseUrl && p.apiKey) {
            return { baseUrl: p.baseUrl, authToken: p.apiKey, source: 'models.json' };
          }
        }
      }
    } catch {}
  }
  // 2. Claude Code global settings (only if models.json didn't provide)
  const claudeSettings = path.join(process.env.HOME, '.claude', 'settings.json');
  if (fs.existsSync(claudeSettings)) {
    try {
      const raw = JSON.parse(fs.readFileSync(claudeSettings, 'utf8'));
      const env = raw.env || {};
      const url = env.ANTHROPIC_BASE_URL || '';
      const token = env.ANTHROPIC_AUTH_TOKEN || '';
      // Only use if it's a recognized zhipu/z.ai endpoint
      if (url && token && (url.includes('bigmodel.cn') || url.includes('z.ai'))) {
        return { baseUrl: url, authToken: token, source: 'claude-settings' };
      }
    } catch {}
  }
  return {};
}

// Read models.json first, then environment variables
const settings = loadCredentialsFromSettings();
const baseUrl = settings.baseUrl || process.env.ANTHROPIC_BASE_URL || '';
const authToken = settings.authToken || process.env.ANTHROPIC_AUTH_TOKEN || '';
const isFromModelsJson = settings.source === 'models.json';

if (!authToken) {
  console.error('Error: ANTHROPIC_AUTH_TOKEN is not set');
  console.error('');
  console.error('Set the environment variable and retry:');
  console.error('  export ANTHROPIC_AUTH_TOKEN="your-token-here"');
  process.exit(1);
}

// Validate ANTHROPIC_BASE_URL
if (!baseUrl) {
  console.error('Error: ANTHROPIC_BASE_URL is not set');
  console.error('');
  console.error('Set the environment variable and retry:');
  console.error('  export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"');
  console.error('  or');
  console.error('  export ANTHROPIC_BASE_URL="https://open.bigmodel.cn/api/anthropic"');
  process.exit(1);
}

// Determine which platform to use
let platform;
let modelUsageUrl;
let toolUsageUrl;
let quotaLimitUrl;

// Extract the base domain from ANTHROPIC_BASE_URL
const parsedBaseUrl = new URL(baseUrl);
const baseDomain = `${parsedBaseUrl.protocol}//${parsedBaseUrl.host}`;

if (baseUrl.includes('api.z.ai')) {
  platform = 'ZAI';
  modelUsageUrl = `${baseDomain}/api/monitor/usage/model-usage`;
  toolUsageUrl = `${baseDomain}/api/monitor/usage/tool-usage`;
  quotaLimitUrl = `${baseDomain}/api/monitor/usage/quota/limit`;
} else if (baseUrl.includes('open.bigmodel.cn') || baseUrl.includes('dev.bigmodel.cn')) {
  platform = 'ZHIPU';
  modelUsageUrl = `${baseDomain}/api/monitor/usage/model-usage`;
  toolUsageUrl = `${baseDomain}/api/monitor/usage/tool-usage`;
  quotaLimitUrl = `${baseDomain}/api/monitor/usage/quota/limit`;
} else {
  // If loaded from models.json, the baseUrl is already validated by the URL parser
  // and we know it contains 'bigmodel.cn' or 'z.ai' from the loader logic
  if (isFromModelsJson) {
    // Trust the baseUrl from models.json - it's already validated in loadCredentialsFromSettings
    platform = baseUrl.includes('z.ai') ? 'ZAI' : 'ZHIPU';
    modelUsageUrl = `${baseDomain}/api/monitor/usage/model-usage`;
    toolUsageUrl = `${baseDomain}/api/monitor/usage/tool-usage`;
    quotaLimitUrl = `${baseDomain}/api/monitor/usage/quota/limit`;
  } else {
    console.error('Error: Unrecognized ANTHROPIC_BASE_URL:', baseUrl);
    console.error('');
    console.error('Supported values:');
    console.error('  - https://api.z.ai/api/anthropic');
    console.error('  - https://open.bigmodel.cn/api/anthropic');
    console.error('  - Or ensure ~/.qclaw/agents/main/agent/models.json contains valid credentials');
    process.exit(1);
  }
}

console.log(`Platform: ${platform}`);
console.log('');
// Time window: from yesterday at the current hour (HH:00:00) to today at the current hour end (HH:59:59).
const now = new Date();
const startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, now.getHours(), 0, 0, 0);
const endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), 59, 59, 999);

// Format dates as yyyy-MM-dd HH:mm:ss
const formatDateTime = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
};

const startTime = formatDateTime(startDate);
const endtime = formatDateTime(endDate);

// Properly encode query parameters
const queryParams = `?startTime=${encodeURIComponent(startTime)}&endTime=${encodeURIComponent(endtime)}`;

// ── 智谱 quota/limit 接口 unit 枚举（已确认，勿再推断） ──
// 背景：智谱官方从未文档化 unit 枚举；glm-usage 等第三方用「TOKENS_LIMIT 里 nextResetTime 最大=周」的启发式，
//       但本账号只返回两条 TOKENS_LIMIT，启发式会出错，故本脚本直接按 unit 映射，不要退回启发式。
// 枚举由散帅于 2026-08-20 确认（原话：一个是五小时，另一个是一周）：
//   type=TOKENS_LIMIT: unit 3 = 小时(5h 窗口), unit 6 = 周(每周窗口)
//   type=TIME_LIMIT:   unit 5 = 月(MCP 月度额度)
// 新增/变更 unit 值时在此表扩展；未知 unit 回退显示原始 "unit:N"，禁止丢弃或误归类。
const UNIT_LABELS = {
  TOKENS_LIMIT: { '3': '5 Hour', '6': '1 Week' },
  TIME_LIMIT: { '5': '1 Month' },
};

const processQuotaLimit = (data) => {
  if (!data || !data.limits) return data;

  data.limits = data.limits.map(item => {
    const period = (UNIT_LABELS[item.type] || {})[String(item.unit)] || `unit:${item.unit}`;
    const prefix = item.type === 'TIME_LIMIT' ? 'MCP' : 'Token';
    const out = {
      type: item.type,
      unit: item.unit,
      number: item.number,
      label: `${prefix} usage(${period})`,
      percentage: item.percentage,
      nextResetTime: item.nextResetTime,
    };
    if (item.type === 'TIME_LIMIT') {
      out.currentUsage = item.currentValue;
      out.total = item.usage;
      out.remaining = item.remaining;
      out.usageDetails = item.usageDetails;
    }
    return out;
  });
  return data;
};

const queryUsage = (apiUrl, label, appendQueryParams = true, postProcessor = null) => {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(apiUrl);
    const options = {
      hostname: parsedUrl.hostname,
      port: 443,
      path: parsedUrl.pathname + (appendQueryParams ? queryParams : ''),
      method: 'GET',
      headers: {
        'Authorization': authToken,
        'Accept-Language': 'en-US,en',
        'Content-Type': 'application/json'
      }
    };

    const req = https.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        if (res.statusCode !== 200) {
          return reject(new Error(`[${label}] HTTP ${res.statusCode}\n${data}`));
        }

        console.log(`${label} data:`);
        console.log('');

        try {
          const json = JSON.parse(data);
          let outputData = json.data || json;
          if (postProcessor && json.data) {
            outputData = postProcessor(json.data);
          }
          console.log(JSON.stringify(outputData));
        } catch (e) {
          console.log('Response body:');
          console.log(data);
        }

        console.log('');
        resolve();
      });
    });

    req.on('error', (error) => {
      reject(error);
    });

    req.end();
  });
};

const run = async () => {
  await queryUsage(modelUsageUrl, 'Model usage');
  await queryUsage(toolUsageUrl, 'Tool usage');
  await queryUsage(quotaLimitUrl, 'Quota limit', false, processQuotaLimit);
};

run().catch((error) => {
  console.error('Request failed:', error.message);
  process.exit(1);
});
