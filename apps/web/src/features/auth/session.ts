"use client";

import { useQuery } from "@tanstack/react-query";

import { ApiClientError, getCurrentUser } from "@/lib/api";

export async function loadSession() {
  try {
    return await getCurrentUser();
  } catch (error) {
    if (error instanceof ApiClientError && error.status === 401) return null;
    throw error;
  }
}

export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: loadSession,
    retry: false,
    staleTime: 30_000,
  });
}
