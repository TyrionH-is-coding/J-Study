import { describe, expect, it, vi } from "vitest";

import {
  ApiClientError,
  createCourseOutlineFormData,
  getCurrentUser,
} from "@/lib/api";

describe("central API client", () => {
  it("builds the course outline multipart contract without a metadata mode", () => {
    const outline = new File(["# Unit One"], "outline.md", {
      type: "text/markdown",
    });
    const pdfs = [
      new File(["%PDF-1.4"], "lecture-one.pdf", { type: "application/pdf" }),
      new File(["%PDF-1.4"], "lecture-two.pdf", { type: "application/pdf" }),
    ];

    const formData = createCourseOutlineFormData({ outline, pdfs });

    expect(formData.get("service_mode")).toBe("course_outline");
    expect(formData.get("outline")).toBe(outline);
    expect(formData.getAll("pdfs")).toEqual(pdfs);
    expect(formData.has("mode")).toBe(false);
  });

  it("uses same-origin cookie credentials for API requests", async () => {
    const fetchMock = vi
      .spyOn(global, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ id: "U1", email: "student@example.com", email_verified: false })));

    await getCurrentUser();

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("preserves backend error details", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid credentials" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getCurrentUser()).rejects.toEqual(
      new ApiClientError("Invalid credentials", 401),
    );
  });
});
