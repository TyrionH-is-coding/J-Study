import { describe, expect, it, vi } from "vitest";

import { ApiError, apiRequest } from "./client";

describe("apiRequest", () => {
  it("uses the relative API boundary and includes cookies", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ready: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const result = await apiRequest<{ ready: boolean }>("health", {}, fetcher);

    expect(result).toEqual({ ready: true });
    expect(fetcher).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("returns undefined for an empty successful response", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));

    await expect(apiRequest<void>("/api/logout", {}, fetcher)).resolves.toBeUndefined();
  });

  it("throws a typed safe error for a failed response", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Request rejected" }), {
        status: 400,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(apiRequest("jobs", {}, fetcher)).rejects.toEqual(
      new ApiError(400, "Request rejected"),
    );
  });
});
