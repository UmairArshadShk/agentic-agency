import { expect, test } from "@playwright/test";

test("start a project, chat with streaming, request changes, then approve", async ({ page }) => {
  const name = `e2e-${Date.now()}`;
  await page.goto("/");

  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Start" }).click();

  // The workflow ran its stages and paused at the gate.
  await expect(page.getByRole("heading", { name })).toBeVisible();
  await expect(page.getByLabel("Stages run")).toContainText("stub_a");
  await expect(page.getByLabel("Stages run")).toContainText("stub_b");
  const gate = page.getByLabel("Approval gate");
  await expect(gate).toBeVisible();

  // Chat reply streams in from the API.
  await page.getByLabel("Message").fill("hello agency");
  await page.getByRole("button", { name: "Send" }).click();
  const conversation = page.getByRole("log", { name: "Conversation" });
  await expect(conversation).toContainText("Received: hello agency.");
  await expect(conversation).toContainText("approval gate");

  // Request changes: the workflow loops and waits at the gate again.
  await gate.getByLabel("Comment for the team").fill("bigger logo");
  await gate.getByRole("button", { name: "Request changes" }).click();
  await expect(conversation).toContainText("Requested changes: bigger logo.");
  await expect(gate).toContainText("revision 1");

  // Approve: the workflow finishes and the gate goes away.
  await gate.getByRole("button", { name: "Approve" }).click();
  await expect(conversation).toContainText("The project finished all stages.");
  await expect(page.getByLabel("Stages run")).toContainText("stub_c");
  await expect(page.getByLabel("Approval gate")).toHaveCount(0);
});

test("chat history survives a page reload", async ({ page }) => {
  const name = `e2e-reload-${Date.now()}`;
  await page.goto("/");
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Start" }).click();
  await page.getByLabel("Message").fill("remember me");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("log")).toContainText("Received: remember me.");

  await page.reload();
  await page.getByRole("button", { name }).click();
  await expect(page.getByRole("log")).toContainText("remember me");
});

test("a slow project-list refresh does not wipe a project that was just created", async ({
  page,
}) => {
  // Hold the first list response until the test releases it, so it arrives after the project
  // was created and shown.
  let release!: () => void;
  const released = new Promise<void>((resolve) => (release = resolve));
  let held = false;
  await page.route("**/projects", async (route) => {
    if (route.request().method() === "GET" && !held) {
      held = true;
      const response = await route.fetch();
      const body = (await response.json()) as { name: string }[];
      await released;
      // Deliver the list as it was before the project existed: a response that is stale by the
      // time it arrives (the server may build it after the create finishes, so strip it here).
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "access-control-allow-origin": "http://127.0.0.1:3001" },
        body: JSON.stringify(body.filter((p) => !p.name.startsWith("e2e-race"))),
      });
    } else {
      await route.continue();
    }
  });

  const name = `e2e-race-${Date.now()}`;
  await page.goto("/");
  await page.getByLabel("New project name").fill(name);
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.getByRole("heading", { name })).toBeVisible();
  expect(held).toBe(true);

  release(); // the stale list (without the project) is delivered to the page now
  await page.waitForTimeout(1000);
  // Plain counts, not retrying assertions: a retrying check would wait for the next poll to put
  // the project back and hide the bug.
  expect(await page.getByText("Start or select a project to begin.").count()).toBe(0);
  expect(await page.getByRole("heading", { name }).count()).toBe(1);
  expect(await page.getByLabel("Approval gate").count()).toBe(1);
});
