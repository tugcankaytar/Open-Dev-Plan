import { useEffect, useState } from "react";
import type { Job } from "../api/types";

const TERMINAL: Job["status"][] = ["succeeded", "failed", "cancelled"];

/** Subscribes to /api/jobs/{id}/stream (SSE) and returns the latest Job
 * state, closing the connection once the job reaches a terminal status. */
export function useJobStream(jobId: string | null): Job | null {
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }
    const source = new EventSource(`/api/jobs/${jobId}/stream`);
    source.onmessage = (event) => {
      const next = JSON.parse(event.data) as Job;
      setJob(next);
      if (TERMINAL.includes(next.status)) {
        source.close();
      }
    };
    source.onerror = () => {
      source.close();
    };
    return () => source.close();
  }, [jobId]);

  return job;
}
