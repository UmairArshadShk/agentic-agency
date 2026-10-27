import { execSync, spawn } from "node:child_process";
import path from "node:path";
import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8000";
const REPO_ROOT = path.resolve(__dirname, "..", "..");

function apiPids(): string[] {
  try {
    return execSync("lsof -ti tcp:8000 -sTCP:LISTEN", { encoding: "utf8" }).split("\n").filter(Boolean);
  } catch {
    return []; // lsof exits non-zero when nothing listens
  }
}

function killApi() {
  for (const pid of apiPids()) process.kill(Number(pid), "SIGKILL");
}

async function waitForApi(up: boolean) {
  await expect
    .poll(async () => (await fetch(`${API}/health`).then((r) => r.ok).catch(() => false)) === up, {
      timeout: 40_000,
    })
    .toBe(true);
}

function startApi() {
  spawn("make", ["api"], { cwd: REPO_ROOT, detached: true, stdio: "ignore" }).unref();
}

test.afterAll(() => {
  // Leave nothing behind: the server this test started is not managed by Playwright.
  killApi();
});

test("a paused project survives a hard server restart and resumes from the UI", async ({ page }) => {
  const name = `e2e-restart-${Date.now()}`;
  await page.goto("/");
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByLabel("Approval gate")).toBeVisible();
  await expect(page.getByLabel("Stages run")).toContainText("stub_b");

  // Stop the server without any chance to shut down cleanly.
  killApi();
  await waitForApi(false);
  await expect(page.getByText("Cannot reach the API")).toBeVisible({ timeout: 15_000 });

  // Start a brand-new server process (new connection pool, new compiled graph).
  startApi();
  await waitForApi(true);
  await expect(page.getByText("Cannot reach the API")).toHaveCount(0, { timeout: 15_000 });

  // The project is still paused at the same gate: reload the page and pick it up again.
  await page.reload();
  await page.getByRole("button", { name }).click();
  const gate = page.getByLabel("Approval gate");
  await expect(gate).toBeVisible();
  await expect(page.getByLabel("Stages run")).toContainText("stub_b");
  await expect(page.getByLabel("Stages run")).not.toContainText("stub_c");

  // Approve after the restart: the workflow continues from where it paused.
  await gate.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("log")).toContainText("The project finished all stages.");
  await expect(page.getByLabel("Stages run")).toContainText("stub_c");
  await expect(page.getByLabel("Approval gate")).toHaveCount(0);
});
