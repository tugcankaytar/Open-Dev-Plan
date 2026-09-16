import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

/** Subscribes once (mount this at the app root) to /api/events — an SSE
 * stream the backend pushes to on ANY write anywhere: a REST call, a
 * chat tool call, a background extraction job finishing. On each
 * message we invalidate the whole React Query cache, so every page
 * refetches automatically — no manual reload, ever, regardless of
 * where the change came from. EventSource reconnects on its own after
 * a transient drop, so there's nothing to do in onerror beyond letting
 * that happen. */
export function useLiveEvents() {
  const queryClient = useQueryClient();

  useEffect(() => {
    const source = new EventSource("/api/events");
    source.onmessage = () => {
      queryClient.invalidateQueries();
    };
    return () => source.close();
  }, [queryClient]);
}
