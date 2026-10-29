import { LABEL_TEXT, city, km, shortDate } from "../format";
import type { Plan } from "../types";

// The finished plan as a gig poster: the one loud element on the page.
export function TourPoster({ plan, active, onSelect }: { plan: Plan; active: number | null; onSelect: (i: number) => void }) {
  return (
    <article aria-labelledby="poster-title" className="rounded-2xl bg-ink p-6 text-white sm:p-8">
      <p className="text-sm text-white/70">
        {plan.on_qloo ? "Tour plan" : `Tour plan, mapped from fans of ${plan.signal_names.join(", ")}`}
      </p>
      <h2 id="poster-title" className="poster-type misregister mt-1 text-[clamp(2.8rem,6vw,4.6rem)]">
        {plan.artist}
      </h2>
      <p className="mt-3 max-w-[60ch] text-white/85">{plan.summary}</p>

      <ol className="mt-6 divide-y divide-white/15">
        {plan.stops.map((s, i) => {
          const d = shortDate(s.date);
          const c = city(s.metro);
          const selected = active === i;
          return (
            <li key={`${s.metro}-${s.date}`}>
              <button
                type="button"
                onClick={() => onSelect(i)}
                aria-pressed={selected}
                className={`grid w-full grid-cols-[3.6rem_1fr] items-baseline gap-x-4 py-3 text-left sm:grid-cols-[3.6rem_1fr_auto] ${
                  selected ? "text-yellow" : "hover:text-yellow"
                }`}
              >
                <span className="font-semibold tabular-nums">
                  {d.month} {d.day}
                  <span className="block text-xs font-normal text-white/60">{d.weekday}</span>
                </span>
                <span>
                  <span className="poster-type text-[clamp(1.6rem,3vw,2.3rem)]">{c.name}</span>
                  <span className="ml-2 text-sm text-white/60">{c.region}</span>
                  <span className="block text-sm text-white/80">
                    {s.venue?.name ?? "Venue to find"}
                    {s.openers[0] && ` with ${s.openers.map((o) => o.name).join(" and ")}`}
                  </span>
                </span>
                <span className="col-start-2 mt-1 text-xs sm:col-start-3 sm:mt-0 sm:text-right">
                  <span className={s.label === "unserved" ? "rounded-full bg-pink px-2 py-0.5 text-white" : "text-white/70"}>
                    {s.label ? LABEL_TEXT[s.label] : ""}
                  </span>
                  {s.travel_day_before && <span className="block text-white/60">travel day before</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <p className="mt-5 text-sm text-white/70">
        {plan.stops.length} shows, {km(plan.total_km)} on the road
        {plan.days_off.length > 0 && `, ${plan.days_off.length} day${plan.days_off.length > 1 ? "s" : ""} off`}
        {plan.dropped.length > 0 && `. Dropped: ${plan.dropped.map((d) => `${d.metro} (${d.reason})`).join(", ")}`}.
      </p>
    </article>
  );
}
