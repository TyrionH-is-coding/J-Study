import { defineConfig } from "@playwright/test";

process.env.JSTUDY_API_ORIGIN = "http://127.0.0.1:8130";
process.env.JSTUDY_E2E_API_PORT = "8130";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: "line",
  use: {
    baseURL: "http://127.0.0.1:3130",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: "python e2e/support/serve_backend.py",
      url: "http://127.0.0.1:8130/api/health",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3130",
      url: "http://127.0.0.1:3130/login",
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
  projects: [
    { name: "mobile-390", use: { viewport: { width: 390, height: 844 } } },
    { name: "tablet-768", use: { viewport: { width: 768, height: 1024 } } },
    { name: "desktop-1440", use: { viewport: { width: 1440, height: 900 } } },
  ],
});
