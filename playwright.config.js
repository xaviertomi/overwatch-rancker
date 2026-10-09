const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/frontend',
  use: { baseURL: 'http://127.0.0.1:4173/overwatch-rancker/', trace: 'retain-on-failure' },
  webServer: { command: 'python tests/frontend/server.py 4173', port: 4173, reuseExistingServer: true },
});
