// Words and numbers as a musician reads them (not as the system names them).

import type { Badge, Label } from "./types";

const STEP_TEXT: Record<string, string> = {
  queue: "Waiting for a free slot",
  intake: "Read your request",
  resolve: "Looked you up on Qloo",
  confirm_artist: "Chose whose fans to map",
  reach: "Added your listener numbers",
  demand: "Mapped where your kind of fans are",
  score: "Compared demand with your reach",
  pick_cities: "Cities confirmed",
  route: "Routed the tour",
  fanout: "Found venues, openers, sponsors and promo spots",
  compose: "Writing the tour brief",
  validate: "Checked every name and number",
  outputs: "Plan ready",
  refine: "Applied your change",
};

export const stepTitle = (node: string) => STEP_TEXT[node] ?? node;

export const LABEL_TEXT: Record<Label, string> = {
  unserved: "Unserved fans",
  proven: "Proven market",
  potential: "Worth a try",
  low: "Low demand",
};

export const BADGE_TEXT: Record<Badge, string> = {
  based_here: "Based here",
  elsewhere: "Based elsewhere",
  unknown: "Hometown unknown",
};

export function city(metro: string): { name: string; region: string } {
  const [name, region = ""] = metro.split(", ");
  return { name, region };
}

export function shortDate(iso: string): { month: string; day: string; weekday: string } {
  const d = new Date(`${iso}T12:00:00`);
  return {
    month: d.toLocaleDateString("en-US", { month: "short" }),
    day: String(d.getDate()),
    weekday: d.toLocaleDateString("en-US", { weekday: "short" }),
  };
}

export const km = (n: number | null | undefined) => (n == null ? "—" : `${n.toLocaleString("en-US")} km`);
export const score = (n: number | null | undefined) => (n == null ? "—" : Math.round(n).toString());
