import { QueryClient } from "@tanstack/react-query";

export function createMayabuQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        gcTime: 10 * 60_000,
        retry: (failureCount, error) => {
          const status =
            typeof error === "object" && error && "status" in error ? Number(error.status) : 0;
          return failureCount < 2 && status !== 404 && status !== 429;
        },
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}
