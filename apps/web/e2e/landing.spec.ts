import { expect, test } from "@playwright/test";

test("landing page states what the product does", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Share documents without sharing yourself" })).toBeVisible();
});
