import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CourseOutlineForm } from "@/features/course-outline/course-outline-form";
import { generateCourseOutline } from "@/lib/api";
import { renderWithQuery } from "@/test/render";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  generateCourseOutline: vi.fn(),
}));

describe("CourseOutlineForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits one outline and repeated PDFs as Course Outline Mode", async () => {
    const user = userEvent.setup();
    vi.mocked(generateCourseOutline).mockResolvedValue({
      job_id: "job-123",
      status: "queued",
      status_url: "/api/jobs/job-123",
    });
    renderWithQuery(<CourseOutlineForm />);
    const outline = new File(["# Unit One"], "outline.md", { type: "text/markdown" });
    const pdfs = [
      new File(["%PDF"], "lecture-one.pdf", { type: "application/pdf" }),
      new File(["%PDF"], "lecture-two.pdf", { type: "application/pdf" }),
    ];

    await user.upload(screen.getByLabelText("Course outline"), outline);
    await user.upload(screen.getByLabelText("Course PDFs"), pdfs);
    const submit = screen.getByRole("button", { name: "Generate material" });
    expect(submit).toBeEnabled();
    fireEvent.submit(submit.closest("form")!);

    await waitFor(() => {
      expect(generateCourseOutline).toHaveBeenCalledWith({ outline, pdfs });
      expect(push).toHaveBeenCalledWith("/jobs/job-123");
    });
  });
});
