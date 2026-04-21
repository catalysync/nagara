'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TooltipProvider } from '@aspect/react';
import { useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  // useState so each mount gets its own client — matters for Next.js RSC
  // hydration where the server and client trees don't share memory.
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
}
