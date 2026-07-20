import { expect, test } from "@playwright/test";
import { BASE_URL, TEST_CHANNEL_ID, login } from "./helpers";

test.beforeEach(async ({ page }) => {
  await login(page);
});

test("login flow redirects to channels", async ({ page }) => {
  await expect(page).toHaveURL(/\/channels$/);
  await expect(page.locator("h1")).toContainText("Channels");
});

test("channels list has no duplicates on mobile", async ({ page }) => {
  await page.goto("/channels");
  await expect(page).toHaveURL(/\/channels$/);

  const tableWrapper = page.locator("div.hidden.overflow-x-auto.sm\\:block");
  await expect(tableWrapper).toBeHidden();

  const cardsSection = page.locator("div.space-y-3.sm\\:hidden");
  await expect(cardsSection).toBeVisible();

  const cards = cardsSection.locator("> div.rounded-lg.border.border-slate-800.bg-slate-900.p-3");
  const cardCount = await cards.count();
  expect(cardCount).toBeGreaterThanOrEqual(1);

  const table = page.locator("table");
  await expect(table).toBeHidden();
});

test("open button on channel card navigates to detail", async ({ page }) => {
  await page.goto("/channels");
  await expect(page).toHaveURL(/\/channels$/);

  const cardsSection = page.locator(".sm\\:hidden");
  const openLink = cardsSection.locator(`a[href="/channels/${TEST_CHANNEL_ID}"]`).filter({
    hasText: "Open",
  });
  await expect(openLink).toBeVisible();
  await openLink.click();

  await page.waitForURL(`**/channels/${TEST_CHANNEL_ID}`);
  await expect(page).toHaveURL(new RegExp(`/channels/${TEST_CHANNEL_ID}$`));

  await expect(page.locator("form")).toBeVisible();
  await expect(page.locator("#rl-pattern")).toBeVisible();
});

test("replace-link form submission redirects to job detail", async ({ page }) => {
  await page.goto(`/channels/${TEST_CHANNEL_ID}`);
  await expect(page.locator("#rl-pattern")).toBeVisible();

  await page.locator("#rl-pattern").fill("https://nonexistent-zzz-test-12345\\.example\\.com");
  await page.locator("#rl-new-link").fill("https://new.example.com");
  await page.locator("#rl-limit").fill("3");
  await page.locator('button[type="submit"]').click();

  await page.waitForURL(/\/jobs\/\d+$/, { timeout: 30_000 });
  await expect(page).toHaveURL(/\/jobs\/\d+$/);
  await expect(page.locator("h1")).toContainText("Job #");
});

test("job detail shows progress bar and reaches terminal status", async ({ page }) => {
  await page.goto(`/channels/${TEST_CHANNEL_ID}`);
  await page.locator("#rl-pattern").fill("https://nonexistent-zzz-test-12345\\.example\\.com");
  await page.locator("#rl-new-link").fill("https://new.example.com");
  await page.locator("#rl-limit").fill("3");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/jobs\/\d+$/, { timeout: 30_000 });

  const progressBar = page.locator(".h-2.w-full.overflow-hidden.rounded-full.bg-slate-800");
  await expect(progressBar).toBeVisible();

  const statusBadge = page.locator(
    ".rounded-md.px-2.py-0\\.5.text-\\[10px\\].font-semibold.uppercase",
  );
  await expect(statusBadge).toBeVisible();

  await expect(statusBadge).toContainText(/done|failed|cancelled/i, { timeout: 30_000 });
});

test("zero-match feedback shows amber alert when total is zero", async ({ page }) => {
  await page.goto(`/channels/${TEST_CHANNEL_ID}`);
  await page.locator("#rl-pattern").fill("https://nonexistent-zzz-test-12345\\.example\\.com");
  await page.locator("#rl-new-link").fill("https://new.example.com");
  await page.locator("#rl-limit").fill("3");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/jobs\/\d+$/, { timeout: 30_000 });

  const statusBadge = page.locator(
    ".rounded-md.px-2.py-0\\.5.text-\\[10px\\].font-semibold.uppercase",
  );
  await expect(statusBadge).toContainText(/done/i, { timeout: 30_000 });

  const zeroMatchAlert = page.locator(".border-amber-900.bg-amber-950");
  await expect(zeroMatchAlert).toBeVisible();
  await expect(zeroMatchAlert).toContainText(/No posts matched/i);
});

test("websocket connection establishes without console errors", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });

  await page.goto(`/channels/${TEST_CHANNEL_ID}`);
  await page.locator("#rl-pattern").fill("https://nonexistent-zzz-test-12345\\.example\\.com");
  await page.locator("#rl-new-link").fill("https://new.example.com");
  await page.locator("#rl-limit").fill("3");
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(/\/jobs\/\d+$/, { timeout: 30_000 });

  await page.waitForFunction(() => {
    const proto = (window as unknown as { WebSocket?: typeof WebSocket }).WebSocket;
    return typeof proto !== "undefined";
  });

  await page.waitForTimeout(2_000);

  const wsErrors = consoleErrors.filter(
    (err) =>
      err.toLowerCase().includes("websocket") ||
      err.toLowerCase().includes("ws") ||
      err.toLowerCase().includes("socket"),
  );
  expect(wsErrors).toHaveLength(0);
});
