import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      staleTime: 1000, // Data considered stale after 1 second
      refetchInterval: 3000, // Real-time polling every 3 seconds globally
      refetchIntervalInBackground: false, // Pause polling when window is minimized/hidden
    },
  },
});
