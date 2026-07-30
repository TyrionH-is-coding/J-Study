import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: false,
    timeout: 120_000,
  },
  projects: [
    {
      name: "mobile",
      use: { viewport: { width: 390, height: 844 } },
    },
    {
      name: "tablet",
      use: { viewport: { width: 768, height: 1024 } },
    },
    {
      name: "desktop",
      use: { viewport: { width: 1440, height: 900 } },
    },
  ],
});
