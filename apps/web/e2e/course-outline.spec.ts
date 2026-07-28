import { expect, test, type Page, type TestInfo } from "@playwright/test";

function twoPagePdf(label: string): Buffer {
  const streams = [1, 2].map((page) => `BT /F1 16 Tf 60 720 Td (${label} page ${page}) Tj ET`);
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>",
    `<< /Length ${Buffer.byteLength(streams[0])} >>\nstream\n${streams[0]}\nendstream`,
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>",
    `<< /Length ${Buffer.byteLength(streams[1])} >>\nstream\n${streams[1]}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let body = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(body));
    body += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = Buffer.byteLength(body);
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  body += offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, "ascii");
}

function collectConsoleErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("status of 401 (Unauthorized)")) {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

async function register(page: Page, testInfo: TestInfo) {
  const email = `${testInfo.project.name}-${testInfo.title.replace(/\W+/g, "-").toLowerCase()}-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/modes$/);
  return email;
}

async function openCourseOutline(page: Page) {
  await page.getByRole("link", { name: /Course Outline/ }).click();
  await expect(page).toHaveURL(/\/modes\/course-outline$/);
}

async function uploadJob(page: Page, pdfNames: string[]) {
  await page.getByLabel("Course outline").setInputFiles({
    name: "outline.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Unit One\n# Unit Two\n", "utf-8"),
  });
  await page.getByLabel("Course PDFs").setInputFiles(
    pdfNames.map((name) => ({ name, mimeType: "application/pdf", buffer: twoPagePdf(name) })),
  );
  await page.getByRole("button", { name: "Generate material" }).click();
  await expect(page).toHaveURL(/\/jobs\/[a-z0-9-]+$/);
}

async function expectNoOverflow(page: Page) {
  const dimensions = await page.getByTestId("app-shell").evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBe(dimensions.clientWidth);
}

test("auth, route guard, mode selector, logout, and login", async ({ page }, testInfo) => {
  const consoleErrors = collectConsoleErrors(page);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  const email = await register(page, testInfo);
  await expect(page.getByRole("link", { name: /Course Outline/ })).toBeVisible();
  await expectNoOverflow(page);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/modes");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/modes$/);
  expect(consoleErrors).toEqual([]);
});

test("submits an outline with one PDF and opens the completed reader", async ({ page }, testInfo) => {
  const consoleErrors = collectConsoleErrors(page);
  await register(page, testInfo);
  await openCourseOutline(page);
  await uploadJob(page, ["lecture-one.pdf"]);
  await expect(page.getByRole("heading", { level: 1, name: "Unit One" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Export Markdown" })).toBeVisible();
  await page.getByRole("button", { name: /Unit Two/ }).click();
  await expect(page.getByText("Weak evidence")).toBeVisible();
  await expectNoOverflow(page);
  expect(consoleErrors).toEqual([]);
});

test("submits two PDFs, switches sources, jumps citation locally, and restores on refresh", async ({ page }, testInfo) => {
  const consoleErrors = collectConsoleErrors(page);
  await page.addInitScript(() => {
    const state = window as typeof window & { __previewScrolls?: number; __windowScrolls?: number };
    state.__previewScrolls = 0;
    state.__windowScrolls = 0;
    window.scrollTo = () => { state.__windowScrolls = (state.__windowScrolls ?? 0) + 1; };
    HTMLElement.prototype.scrollTo = function () {
      if (this.getAttribute("data-testid") === "source-preview-scroll") state.__previewScrolls = (state.__previewScrolls ?? 0) + 1;
    };
  });
  await register(page, testInfo);
  await openCourseOutline(page);
  await uploadJob(page, ["lecture-one.pdf", "lecture-two.pdf"]);
  await expect(page.getByRole("heading", { level: 1, name: "Unit One" })).toBeVisible();
  await page.getByRole("combobox", { name: "Source" }).selectOption("S001");
  await expect(page.getByAltText("lecture-one.pdf page 1")).toBeVisible();
  await page.getByRole("button", { name: "Open citation E001" }).click();
  await expect(page.getByRole("combobox", { name: "Source" })).toHaveValue("S002");
  await expect(page.getByAltText("lecture-two.pdf page 2")).toBeVisible();
  const scrollState = await page.evaluate(() => {
    const state = window as typeof window & { __previewScrolls?: number; __windowScrolls?: number };
    return { preview: state.__previewScrolls, window: state.__windowScrolls };
  });
  expect(scrollState.preview).toBeGreaterThan(0);
  expect(scrollState.window).toBe(0);
  const jobUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(jobUrl);
  await expect(page.getByRole("heading", { level: 1, name: "Unit One" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Source" }).locator("option")).toHaveCount(2);
  await expectNoOverflow(page);
  await page.screenshot({ path: testInfo.outputPath("reader.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("shows a failed backend job state", async ({ page }, testInfo) => {
  const consoleErrors = collectConsoleErrors(page);
  await register(page, testInfo);
  await openCourseOutline(page);
  await uploadJob(page, ["fail.pdf"]);
  await expect(page.getByText("Generation failed")).toBeVisible();
  await expect(page.getByText(/deterministic E2E generation failure/)).toBeVisible();
  expect(consoleErrors).toEqual([]);
});
