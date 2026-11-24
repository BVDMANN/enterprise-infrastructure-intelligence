import { test, expect } from "@playwright/test";

/**
 * PHASE 0 placeholder spec.
 * The dashboard is a skeleton (loading / error / empty states only) until
 * PHASE 1. This spec asserts the page renders and shows the empty state
 * when the API is reachable; it is skipped until the stack runs.
 */
test.describe("dashboard skeleton", () => {
  test.skip(
    true,
    "PHASE 1: requires web + api running via docker compose (Docker absent on this VM).",
  );

  test("shows the empty state when no infrastructure is connected", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(
      page.getByText("No infrastructure connected"),
    ).toBeVisible();
    await expect(
      page.getByText("Enterprise Infrastructure Intelligence"),
    ).toBeVisible();
  });
});
