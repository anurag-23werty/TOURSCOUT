import { useState } from "react";
import { api } from "../api";
import { city } from "../format";
import type { BaselineStop, Message, Plan } from "../types";

export function Compare({ plan, threadId }: { plan: Plan; threadId: string }) {
  const [baseline, setBaseline] = useState<BaselineStop[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setBaseline((await api.compare(threadId)).llm_only.stops);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't run the comparison.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="compare-title" className="space-y-4">
      <div>
        <h2 id="compare-title" className="font-display text-2xl font-bold">
          Same request, no Qloo
        </h2>
        <p className="max-w-[60ch] text-ink-soft">
          A language model on its own plans from memory: big-name cities and venues, no idea where your fans actually are,
          and nothing checked against data. Run it to see the difference.
        </p>
      </div>
      {!baseline && (
        <button type="button" onClick={run} disabled={busy} className="rounded-full border-2 border-ink px-5 py-2 font-semibold hover:bg-ink hover:text-white disabled:opacity-50">
          {busy ? "Asking the model…" : "Run the LLM-only plan"}
        </button>
      )}
      {error && <p role="alert" className="text-pink-deep">{error}</p>}
      {baseline && (
        <div className="grid gap-4 md:grid-cols-2">
          <Column title="TourScout" note="Cities from your fans' demand map; every venue and opener is a Qloo entity.">
            {plan.stops.map((s) => (
              <Row key={s.date + s.metro} city={city(s.metro).name} venue={s.venue?.name ?? "venue to find"} openers={s.openers.map((o) => o.name)} />
            ))}
          </Column>
          <Column title="LLM only" note="Names are from the model's memory and weren't checked: some may be closed or invented.">
            {baseline.map((s) => (
              <Row key={s.date + s.city} city={s.city} venue={s.venue} openers={s.openers} />
            ))}
          </Column>
        </div>
      )}
    </section>
  );
}

function Column({ title, note, children }: { title: string; note: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl bg-sheet p-4">
      <h3 className="font-display text-lg font-bold">{title}</h3>
      <p className="text-xs text-ink-soft">{note}</p>
      <ul className="mt-3 divide-y divide-line">{children}</ul>
    </div>
  );
}

function Row({ city: name, venue, openers }: { city: string; venue: string; openers: string[] }) {
  return (
    <li className="py-2 text-sm">
      <span className="font-semibold">{name}</span>, {venue}
      {openers.length > 0 && <span className="block text-ink-soft">with {openers.join(", ")}</span>}
    </li>
  );
}

export function Outreach({ plan }: { plan: Plan }) {
  const items: [string, Message | undefined][] = [
    [`Sponsor pitch to ${plan.outreach.sponsor_pitch?.brand ?? "a brand"}`, plan.outreach.sponsor_pitch],
    [`Message to ${plan.outreach.opener_dm?.opener ?? "an opener"}`, plan.outreach.opener_dm],
  ];
  return (
    <section aria-labelledby="outreach-title" className="space-y-4">
      <h2 id="outreach-title" className="font-display text-2xl font-bold">
        Drafts to send
      </h2>
      <p className="text-ink-soft">{plan.sponsor_strategy}</p>
      {items.map(([title, msg]) =>
        msg ? (
          <article key={title} className="rounded-2xl bg-sheet p-4">
            <h3 className="font-semibold">{title}</h3>
            <p className="mt-1 text-sm text-ink-soft">Subject: {msg.subject}</p>
            <p className="mt-2 whitespace-pre-line text-sm">{msg.body}</p>
            <button type="button" onClick={() => navigator.clipboard.writeText(`${msg.subject}\n\n${msg.body}`)} className="mt-3 text-sm font-semibold underline underline-offset-4">
              Copy
            </button>
          </article>
        ) : null,
      )}
      {plan.risks.length > 0 && (
        <div>
          <h3 className="font-semibold">Check before booking</h3>
          <ul className="list-disc pl-5 text-sm text-ink-soft">
            {plan.risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
