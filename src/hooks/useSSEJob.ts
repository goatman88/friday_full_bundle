// src/hooks/useSSEJob.ts
import API_BASE from "../lib/apiBase";

export type JobUpdate = {
  ok: boolean;
  job?: { status: string; progress: number; message?: string; updated_at?: number; title?: string };
  error?: string;
};

export function useSSEJob(jobId: string | null, onUpdate: (u: JobUpdate) => void) {
  // Returns a cleanup function; you can also check support
  let es: EventSource | null = null;

  function start() {
    if (!jobId || !API_BASE || typeof window === "undefined") return;
    if (!("EventSource" in window)) return; // no SSE support, caller should fall back to polling

    es = new EventSource(`${API_BASE}/api/rag/stream/${encodeURIComponent(jobId)}`, {
      withCredentials: false
    } as any);

    es.addEventListener("update", (e: MessageEvent) => {
      try {
        const data: JobUpdate = JSON.parse(e.data);
        onUpdate(data);
      } catch {
        // ignore
      }
    });

    es.onerror = () => {
      // On error, close—caller can switch to polling
      es?.close();
      es = null;
    };
  }

  function stop() {
    es?.close();
    es = null;
  }

  return { start, stop, supported: typeof window !== "undefined" && "EventSource" in window };
}
