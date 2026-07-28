import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthForm } from "@/features/auth/auth-form";
import { login } from "@/lib/api";
import { renderWithQuery } from "@/test/render";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  login: vi.fn(),
  register: vi.fn(),
}));

describe("AuthForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("logs in with the backend cookie flow and opens the mode selector", async () => {
    vi.mocked(login).mockResolvedValue({
      id: "U1",
      email: "student@example.com",
      email_verified: false,
    });
    renderWithQuery(<AuthForm mode="login" />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "student@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "password123" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith("student@example.com", "password123");
      expect(replace).toHaveBeenCalledWith("/modes");
    });
  });
});
