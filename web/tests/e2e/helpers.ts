import type { Page } from "@playwright/test";

export const BASE_URL = "http://docker-dind:8080";

export const TEST_CHANNEL_ID = 2;

export const TEST_USERNAME = "admin";
export const TEST_PASSWORD = "admin";

export async function login(
  page: Page,
  username: string = TEST_USERNAME,
  password: string = TEST_PASSWORD,
): Promise<void> {
  await page.goto("/login");
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await page.locator('button[type="submit"]').click();
  await page.waitForURL("**/channels");
}

export async function getSessionCookie(page: Page): Promise<string | null> {
  const cookies = await page.context().cookies();
  const session = cookies.find((c) => c.name === "session");
  return session ? session.value : null;
}
