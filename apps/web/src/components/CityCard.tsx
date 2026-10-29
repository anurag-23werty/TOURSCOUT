import { useState } from "react";
import { api } from "../api";
import { BADGE_TEXT, LABEL_TEXT, score } from "../format";
import type { Message, Stop } from "../types";

const KIND_TEXT: Record<string, string> = { record_store: "Record store", coffee_shop: "Café", book_store: "Bookshop", bar: "Bar" };

export function CityCard({ stop, threadId }: { stop: Stop; threadId: string }) {
  const [dm, setDm] = useState<Message | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function writeDm() {
    setBusy(true);
    setError(null);
    try {
      setDm(await api.outreach(threadId, { kind: "opener", metro: stop.metro }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't write the message.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article aria-labelledby="city-title" className="space-y-5 rounded-2xl bg-sheet p-5">
      <header>
        <h3 id="city-title" className="font-display text-2xl font-bold">
          {stop.metro}
        </h3>
        <p className="text-sm text-ink-soft">
          {stop.label ? LABEL_TEXT[stop.label] : "Show"} on {stop.date}: demand {score(stop.demand)}, your reach {score(stop.reach)}
        </p>
        <p className="mt-2">{stop.why}</p>
      </header>

      <div>
        <h4 className="text-sm font-semibold">Venue</h4>
        {stop.venue ? (
          <p>
            <span className="font-medium">{stop.venue.name}</span>
            {stop.venue.rating != null && <span className="text-ink-soft">, rated {stop.venue.rating.toFixed(1)}</span>}
            <span className="block text-sm text-ink-soft">{stop.venue.address}</span>
            <span className="block text-sm text-ink-soft">Capacity isn't in the data: check it with the venue.</span>
          </p>
        ) : (
          <p className="text-ink-soft">Qloo has no venue for this city yet: ask local promoters.</p>
        )}
        {stop.backup_venues.length > 0 && (
          <p className="mt-1 text-sm text-ink-soft">Backups: {stop.backup_venues.map((v) => v.name).join(", ")}</p>
        )}
      </div>

      <div>
        <h4 className="text-sm font-semibold">Openers</h4>
        {stop.openers.length ? (
          <ul className="space-y-1">
            {stop.openers.map((o) => (
              <li key={o.id}>
                <span className="font-medium">{o.name}</span>
                <span className={`ml-2 rounded-full px-2 py-0.5 text-xs ${o.badge === "based_here" ? "bg-yellow/60" : "bg-paper text-ink-soft"}`}>
                  {o.badge ? BADGE_TEXT[o.badge] : BADGE_TEXT.unknown}
                  {o.badge === "elsewhere" && o.home ? `: ${o.home}` : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-ink-soft">No smaller act with your fans' taste found here.</p>
        )}
        {stop.openers.length > 0 && (
          <button type="button" onClick={writeDm} disabled={busy} className="mt-2 text-sm font-semibold text-pink-deep underline underline-offset-4 disabled:opacity-50">
            {busy ? "Writing…" : `Write a message to ${stop.openers[0].name}`}
          </button>
        )}
        {error && <p role="alert" className="text-sm text-pink-deep">{error}</p>}
        {dm && (
          <div className="mt-2 rounded-lg bg-paper p-3 text-sm">
            <p className="font-semibold">{dm.subject}</p>
            <p className="mt-1 whitespace-pre-line">{dm.body}</p>
            <button type="button" onClick={() => navigator.clipboard.writeText(dm.body)} className="mt-2 text-xs font-semibold underline">
              Copy message
            </button>
          </div>
        )}
      </div>

      {stop.sponsors.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold">Brands your fans here love</h4>
          <ul className="text-sm">
            {stop.sponsors.map((b) => (
              <li key={b.id}>
                {b.name}
                <span className="text-ink-soft">{b.new_in_city ? ", shows up only in this city" : b.uplift != null ? `, city uplift ${b.uplift > 0 ? "+" : ""}${b.uplift}` : ""}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {stop.promo.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold">Where to put up posters</h4>
          <ul className="text-sm">
            {stop.promo.map((p) => (
              <li key={p.id}>
                {p.name} <span className="text-ink-soft">({KIND_TEXT[p.kind ?? ""] ?? "spot"})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
