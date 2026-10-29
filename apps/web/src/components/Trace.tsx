import { stepTitle } from "../format";
import type { StepEvent } from "../types";

// The agent's steps as they stream in: a real sequence, so the list is ordered.
export function Trace({ steps, working }: { steps: StepEvent[]; working: boolean }) {
  if (steps.length === 0 && !working) return null;
  return (
    <section aria-label="What TourScout is doing" aria-live="polite">
      <ol className="relative space-y-3 border-l-2 border-line pl-5">
        {steps.map((s, i) => (
          <li key={i} className="relative">
            <span
              aria-hidden
              className={`absolute -left-[27px] top-1.5 size-3 rounded-full border-2 border-paper ${
                s.node === "validate" && s.message.includes("problems") ? "bg-yellow" : "bg-ink"
              }`}
            />
            <p className="text-sm font-semibold">{stepTitle(s.node)}</p>
            <p className="text-sm text-ink-soft">{s.message}</p>
          </li>
        ))}
        {working && (
          <li className="relative">
            <span aria-hidden className="absolute -left-[27px] top-1.5 size-3 animate-pulse rounded-full bg-pink" />
            <p className="text-sm text-ink-soft">Working…</p>
          </li>
        )}
      </ol>
    </section>
  );
}
