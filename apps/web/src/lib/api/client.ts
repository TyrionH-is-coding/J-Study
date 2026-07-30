export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Fetcher = typeof fetch;

function apiPath(path: string) {
  if (path.startsWith("/api/")) {
    return path;
  }
  return `/api/${path.replace(/^\/+/, "")}`;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  fetcher: Fetcher = fetch,
): Promise<T> {
  const response = await fetcher(apiPath(path), {
    ...init,
    credentials: "include",
    headers: {
      accept: "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    let message = "Request failed";
    if (response.headers.get("content-type")?.includes("application/json")) {
      const body = (await response.json()) as { detail?: unknown; message?: unknown };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (typeof body.message === "string") {
        message = body.message;
      }
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.headers.get("content-type")?.includes("application/json")) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
