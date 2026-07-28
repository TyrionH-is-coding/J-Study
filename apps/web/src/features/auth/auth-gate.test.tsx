import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthGate } from "@/features/auth/auth-gate";
import { ApiClientError, getCurrentUser } from "@/lib/api";
import { renderWithQuery } from "@/test/render";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getCurrentUser: vi.fn(),
}));

describe("AuthGate", () => {
  beforeEach(() => vi.clearAllMocks());

  it("redirects unauthenticated users to login", async () => {
    vi.mocked(getCurrentUser).mockRejectedValue(new ApiClientError("Not authenticated", 401));

    renderWithQuery(<AuthGate><div>Private workspace</div></AuthGate>);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("Private workspace")).not.toBeInTheDocument();
  });

  it("renders protected content after the session resolves", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue({ id: "U1", email: "student@example.com", email_verified: false });

    renderWithQuery(<AuthGate><div>Private workspace</div></AuthGate>);

    expect(await screen.findByText("Private workspace")).toBeInTheDocument();
  });
});
