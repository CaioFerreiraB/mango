import { QueryClient } from "@tanstack/react-query"

/** Estado de servidor (contas, transações, …) é gerido pelo TanStack Query (§5.3). */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
