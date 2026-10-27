import { defineConfig } from "@playwright/test";

// End-to-end checks drive the real UI against the real API (needs `make up && make migrate`).
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  timeout: 60_000,
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3001", headless: true },
  webServer: [
    {
      command: "make api",
      cwd: "..",
      url: "http://127.0.0.1:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "pnpm dev",
      url: "http://127.0.0.1:3001",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
