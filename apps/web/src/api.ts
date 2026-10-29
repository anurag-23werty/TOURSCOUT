// Thin client for the TourScout API. Streaming calls are POSTs, so they're read with fetch + a small SSE parser
// (the browser's EventSource only does GET).

import { apiToken, forgetToken } from "./auth";
import type { BaselineStop, Message, MyPlan, Persona, Plan, PlanState, StreamEvent } from "./types";

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

// Guests get an anonymous session id. It's kept in localStorage so a reload (or the round trip through Google sign-in)
// doesn't lose it: after sign-in, the tours planned under it move into the account.
const GUEST_KEY = "tourscout.guest-session";
let sessionId: string | null = null;

function storedGuest(): string | null {
  try {
    return localStorage.getItem(GUEST_KEY);
  } catch {
    return null;
  }
}

function storeGuest(id: string | null) {
  try {
    if (id) localStorage.setItem(GUEST_KEY, id);
    else localStorage.removeItem(GUEST_KEY);
  } catch {
    /* private mode: the session lives in memory only */
  }
}

async function ensureSession(): Promise<string> {
  sessionId ??= storedGuest();
  if (sessionId) return sessionId;
  const res = await fetch(`${API_URL}/api/sessions`, { method: "POST" });
  if (!res.ok) throw await toError(res);
  sessionId = (await res.json()).session_id as string;
  storeGuest(sessionId);
  return sessionId;
}

/** Signed in: `Authorization: Bearer`. Guest: `X-Session-Id`. */
async function identify(headers: Headers): Promise<void> {
  const token = await apiToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  else headers.set("X-Session-Id", await ensureSession());
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
  const headers = new Headers(init.headers);
  await identify(headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (res.status === 401 && !retried) {
    // Signed in: the token was refused (expired/rotated), fetch a fresh one. Guest: the session expired (6 h) or the
    // server restarted, start a new one. Either way, retry once.
    if (headers.has("Authorization")) forgetToken();
    else {
      sessionId = null;
      storeGuest(null);
    }
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

  /** Download the CSV / calendar file (fetched with the right identity, then saved). */
  download: async (threadId: string, fmt: "csv" | "ics") => {
    const res = await call<Response>(`/api/plans/${threadId}/export.${fmt}`);
    const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? `tourscout.${fmt}`;
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: name });
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },

  myPlans: async () => (await call<Response>("/api/me/plans")).json() as Promise<MyPlan[]>,

  rename: (threadId: string, title: string) =>
    call<Response>(`/api/plans/${threadId}`, { method: "PATCH", body: JSON.stringify({ title }) }),

  remove: (threadId: string) => call<Response>(`/api/plans/${threadId}`, { method: "DELETE" }),

  /** Right after sign-in: move this browser's guest tours into the account, then stop using the guest session. */
  claimGuestTours: async (): Promise<number> => {
    const guest = sessionId ?? storedGuest();
    if (!guest) return 0;
    const res = await call<Response>("/api/me/claim", { method: "POST", body: JSON.stringify({ session_id: guest }) });
    sessionId = null;
    storeGuest(null);
    return ((await res.json()) as { moved: number }).moved;
  },

  deleteAccount: () => call<Response>("/api/me", { method: "DELETE" }),
};
