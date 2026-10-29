// One tour-planning run: start → (checkpoints) → plan → refine. Mirrors the agent's SSE stream.

import { useCallback, useRef, useState } from "react";
import { ApiError, api } from "./api";
import type { Checkpoint, MetroRow, Plan, StepEvent, StreamEvent } from "./types";

export type Phase = "idle" | "running" | "waiting" | "done" | "error";

export interface TourRun {
  phase: Phase;
  threadId: string | null;
  steps: StepEvent[];
  checkpoint: Checkpoint | null;
  plan: Plan | null;
  metros: MetroRow[];
  error: string | null;
}

const EMPTY: TourRun = { phase: "idle", threadId: null, steps: [], checkpoint: null, plan: null, metros: [], error: null };

export function useTour() {
  const [run, setRun] = useState<TourRun>(EMPTY);
  const threadRef = useRef<string | null>(null);

  const onEvent = useCallback((e: StreamEvent) => {
    if (e.kind === "thread") threadRef.current = e.data.thread_id;
    setRun((r) => {
      switch (e.kind) {
        case "thread":
          return { ...r, threadId: e.data.thread_id };
        case "step":
          return { ...r, steps: [...r.steps, e.data] };
        case "interrupt":
          return { ...r, phase: "waiting", checkpoint: e.data };
        case "plan":
          return { ...r, phase: "done", plan: e.data, checkpoint: null };
        case "error":
          return { ...r, phase: "error", error: e.data.message };
      }
    });
  }, []);

  // After a pause or a finished plan, fetch the scored metros (with coordinates) for the map.
  const refreshMetros = useCallback(async () => {
    if (!threadRef.current) return;
    try {
      const state = await api.state(threadRef.current);
      setRun((r) => ({ ...r, metros: state.metros }));
    } catch {
      /* the map just stays as it was */
    }
  }, []);

  const guard = useCallback(
    async (work: () => Promise<void>) => {
      try {
        await work();
        await refreshMetros();
      } catch (err) {
        const message =
          err instanceof ApiError && err.status === 429
            ? `${err.message}${err.retryAfter ? ` (about ${Math.ceil(err.retryAfter / 60)} min)` : ""}`
            : err instanceof Error && err.message.includes("fetch")
              ? "Can't reach the TourScout API. Check that it's running and that VITE_API_URL points to it."
              : err instanceof Error
                ? err.message
                : "Something went wrong.";
        setRun((r) => ({ ...r, phase: "error", error: message }));
      }
    },
    [refreshMetros],
  );

  const start = useCallback(
    (body: { message?: string; persona_id?: string; upload_id?: string; auto_approve: boolean }) => {
      threadRef.current = null;
      setRun({ ...EMPTY, phase: "running" });
      return guard(() => api.startPlan(body, onEvent));
    },
    [guard, onEvent],
  );

  const answer = useCallback(
    (value: Record<string, unknown>) => {
      const id = threadRef.current;
      if (!id) return Promise.resolve();
      setRun((r) => ({ ...r, phase: "running", checkpoint: null }));
      return guard(() => api.resume(id, value, onEvent));
    },
    [guard, onEvent],
  );

  const refine = useCallback(
    (message: string) => {
      const id = threadRef.current;
      if (!id) return Promise.resolve();
      setRun((r) => ({ ...r, phase: "running", steps: [...r.steps, { node: "refine", message: `“${message}”` }] }));
      return guard(() => api.refine(id, message, onEvent));
    },
    [guard, onEvent],
  );

  const reset = useCallback(() => {
    threadRef.current = null;
    setRun(EMPTY);
  }, []);

  return { run, start, answer, refine, reset };
}
