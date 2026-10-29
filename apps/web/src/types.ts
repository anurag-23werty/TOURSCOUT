// Shapes returned by the TourScout API (apps/api/tourscout_api). Kept in one place so the UI matches docs/api.md.

export type Label = "unserved" | "proven" | "potential" | "low";
export type Badge = "based_here" | "elsewhere" | "unknown";

export interface Persona {
  id: string;
  artist: string;
  home_base: string;
  regions: string[];
  n_shows: number;
  window: [string, string] | null;
  sounds_like: string[];
  featured: boolean;
}

export interface Venue {
  id: string;
  name: string;
  address?: string | null;
  rating?: number | null;
  affinity?: number | null;
}

export interface Opener {
  id: string;
  name: string;
  badge?: Badge;
  home?: string | null;
  fit?: number;
  score?: number;
  popularity?: number;
}

export interface Brand {
  id: string;
  name: string;
  affinity?: number | null;
  uplift?: number | null;
  new_in_city?: boolean;
}

export interface Spot {
  id: string;
  name: string;
  kind?: string;
  address?: string | null;
}

export interface Stop {
  date: string;
  metro: string;
  lat: number | null;
  lon: number | null;
  drive_km: number | null;
  travel_day_before: boolean;
  label: Label | null;
  demand: number | null;
  reach: number | null;
  gap: number | null;
  venue: Venue | null;
  backup_venues: Venue[];
  openers: Opener[];
  sponsors: Brand[];
  promo: Spot[];
  why: string;
}

export interface Message {
  subject: string;
  body: string;
  brand?: string;
  opener?: string;
  city?: string;
}

export interface Plan {
  artist: string;
  on_qloo: boolean;
  signal_names: string[];
  headline: string;
  summary: string;
  sponsor_strategy: string;
  risks: string[];
  stops: Stop[];
  days_off: string[];
  dropped: { metro: string; reason: string }[];
  total_km: number;
  composed_by: string;
  outreach: { sponsor_pitch?: Message; opener_dm?: Message; errors?: string[] };
}

export interface MetroRow {
  metro: string;
  lat: number;
  lon: number;
  population: number;
  demand: number;
  reach: number;
  gap: number;
  label: Label;
  listeners?: number | null;
}

export interface Candidate {
  id: string;
  name: string;
  popularity: number | null;
  genres: string[];
}

export type Checkpoint =
  | { type: "confirm_artist"; question: string; candidates: Candidate[]; sounds_like: string[] }
  | {
      type: "pick_cities";
      question: string;
      selected: string[];
      metros: Pick<MetroRow, "metro" | "demand" | "reach" | "gap" | "label">[];
    };

export interface StepEvent {
  node: string;
  message: string;
  data?: Record<string, unknown>;
}

export type StreamEvent =
  | { kind: "thread"; data: { thread_id: string } }
  | { kind: "step"; data: StepEvent }
  | { kind: "interrupt"; data: Checkpoint }
  | { kind: "plan"; data: Plan }
  | { kind: "error"; data: { message: string } };

export interface PlanState {
  thread_id: string;
  status: "done" | "waiting" | "running";
  interrupt: Checkpoint | null;
  plan: Plan | null;
  metros: MetroRow[];
  events: StepEvent[];
  llm_calls: { purpose: string; provider: string; model: string; model_version: string | null; seconds: number; ok: boolean }[];
}

export interface BaselineStop {
  city: string;
  date: string;
  venue: string;
  openers: string[];
  sponsors: string[];
  why: string;
}
