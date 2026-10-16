import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: "http://127.0.0.1:5173", trace: "retain-on-failure" },
  webServer: [
    {
      command: "../.venv/bin/python -m uvicorn app.main:app --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: true,
      timeout: 60_000,
      env: {
        DATABASE_URL: "sqlite:///./e2e.db",
        INVESTIGATION_EAGER: "true",
        AUTO_CREATE: "true",
        SEED_ON_STARTUP: "true",
        DEMO_MODE: "true",
        SECRET_KEY: "e2e-secret",
        ANALYST_EMAIL: "analyst@piae.test",
        ANALYST_PASSWORD: "changeme-dev-only",
        ADMIN_PASSWORD: "changeme-admin-dev-only",
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1373, height: 647 } } },
  ],
})
