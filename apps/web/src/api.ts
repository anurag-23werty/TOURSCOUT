// Thin client for the TourScout API. Streaming calls are POSTs, so they're read with fetch + a small SSE parser
// (the browser's EventSource only does GET).

import type { BaselineStop, Message, Persona, Plan, PlanState, StreamEvent } from "./types";

export const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryAfter?: number,
  ) {
    super(message);
  }
}

let sessionId: string | null = null;

async function ensureSession(): Promise<string> {
  if (sessionId) return sessionId;
  const res = await fetch(`${API_URL}/api/sessions`, { method: "POST" });
  if (!res.ok) throw await toError(res);
  sessionId = (await res.json()).session_id as string;
  return sessionId;
}

async function toError(res: Response): Promise<ApiError> {
  let detail = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    /* not JSON */
  }
  const retry = res.headers.get("Retry-After");
  return new ApiError(detail, res.status, retry ? Number(retry) : undefined);
}

async function call<T>(path: string, init: RequestInit = {}, retried = false): Promise<T> {
  const sid = await ensureSession();
  const headers = new Headers(init.headers);
  headers.set("X-Session-Id", sid);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (res.status === 401 && !retried) {
    sessionId = null; // the session expired (6 h) or the server restarted: start a new one once
    return call<T>(path, init, true);
  }
  if (!res.ok) throw await toError(res);
  return res as unknown as T;
}

/** Parse a text/event-stream body into events. Exported for tests. */
export function parseSse(buffer: string): { events: StreamEvent[]; rest: string } {
  const events: StreamEvent[] = [];
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    let kind = "";
    let data = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event: ")) kind = line.slice(7);
      else if (line.startsWith("data: ")) data += line.slice(6);
    }
    if (kind && data) events.push({ kind, data: JSON.parse(data) } as StreamEvent);
  }
  return { events, rest };
}

async function stream(path: string, body: unknown, onEvent: (e: StreamEvent) => void, signal?: AbortSignal) {
  const res = await call<Response>(path, { method: "POST", body: JSON.stringify(body), signal });
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    const parsed = parseSse(buffer + value);
    buffer = parsed.rest;
    parsed.events.forEach(onEvent);
  }
}

export const api = {
  personas: async () => (await call<Response>("/api/personas")).json() as Promise<Persona[]>,

  upload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await call<Response>("/api/upload", { method: "POST", body: form });
    return res.json() as Promise<{ upload_id: string; preview: { kind: string; rows?: { city: string; listeners: number }[]; total_rows?: number; note?: string } }>;
  },

  startPlan: (
    body: { message?: string; persona_id?: string; upload_id?: string; auto_approve: boolean },
    onEvent: (e: StreamEvent) => void,
    signal?: AbortSignal,
  ) => stream("/api/plans", body, onEvent, signal),

  resume: (threadId: string, answer: Record<string, unknown>, onEvent: (e: StreamEvent) => void) =>
    stream(`/api/plans/${threadId}/resume`, { answer }, onEvent),

  refine: (threadId: string, message: string, onEvent: (e: StreamEvent) => void) =>
    stream(`/api/plans/${threadId}/refine`, { message }, onEvent),

  state: async (threadId: string) => (await call<Response>(`/api/plans/${threadId}`)).json() as Promise<PlanState>,

  compare: async (threadId: string) =>
    (await call<Response>(`/api/plans/${threadId}/compare`, { method: "POST" })).json() as Promise<{
      tourscout: Plan;
      llm_only: { stops: BaselineStop[] };
    }>,

  outreach: async (threadId: string, body: { kind: "sponsor"; brand_id: string } | { kind: "opener"; metro: string }) =>
    (await call<Response>(`/api/plans/${threadId}/outreach`, { method: "POST", body: JSON.stringify(body) })).json() as Promise<Message>,

  exportUrl: (threadId: string, fmt: "csv" | "ics") =>
    `${API_URL}/api/plans/${threadId}/export.${fmt}?session_id=${encodeURIComponent(sessionId ?? "")}`,
};
