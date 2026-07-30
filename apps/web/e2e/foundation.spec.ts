import { expect, test } from "@playwright/test";

const routes = [
  ["/", "Frontend foundation is ready."],
  ["/login", "Login"],
  ["/register", "Register"],
  ["/modes", "Learning modes"],
  ["/modes/course-outline", "Course outline"],
  ["/jobs/example-job", "Job example-job"],
] as const;

test("all foundation routes render without console errors or horizontal overflow", async ({
  page,
}) => {
  const errors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));

  for (const [path, heading] of routes) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: heading })).toBeVisible();

    const dimensions = await page.locator("html").evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }));

    expect(dimensions.scrollWidth).toBe(dimensions.clientWidth);
  }

  expect(errors).toEqual([]);
});

test("primary navigation reaches the mode foundation", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Modes", exact: true }).click();

  await expect(page).toHaveURL(/\/modes$/);
  await expect(
    page.getByRole("heading", { name: "Learning modes" }),
  ).toBeVisible();
});
