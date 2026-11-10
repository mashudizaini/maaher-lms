import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', workers: 1, retries: 0, timeout: 45000,
  use: { baseURL: process.env.APP_ORIGIN, browserName: 'chromium',
    channel: process.env.PLAYWRIGHT_CHANNEL,
    launchOptions: process.env.PLAYWRIGHT_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : undefined,
    trace: 'off', screenshot: 'off', video: 'off' },
});
