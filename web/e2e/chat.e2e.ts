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
