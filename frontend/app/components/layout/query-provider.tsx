import { QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { createMayabuQueryClient } from "~/lib/query/client";

export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(createMayabuQueryClient);
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
