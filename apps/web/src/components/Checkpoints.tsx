import { useState } from "react";
import { LABEL_TEXT } from "../format";
import type { Checkpoint } from "../types";

type Answer = (value: Record<string, unknown>) => void;

export function CheckpointCard({ checkpoint, onAnswer }: { checkpoint: Checkpoint; onAnswer: Answer }) {
  return (
    <section aria-labelledby="checkpoint-title" className="rounded-2xl border-2 border-ink bg-sheet p-5">
      <h2 id="checkpoint-title" className="font-display text-xl font-bold">
        {checkpoint.type === "confirm_artist" ? checkpoint.question : "Pick your cities"}
      </h2>
      {checkpoint.type === "confirm_artist" ? (
        <ConfirmArtist checkpoint={checkpoint} onAnswer={onAnswer} />
      ) : (
        <PickCities checkpoint={checkpoint} onAnswer={onAnswer} />
      )}
    </section>
  );
}

function ConfirmArtist({ checkpoint, onAnswer }: { checkpoint: Extract<Checkpoint, { type: "confirm_artist" }>; onAnswer: Answer }) {
  const [choice, setChoice] = useState<string>(checkpoint.candidates[0]?.id ?? "none");
  const [soundsLike, setSoundsLike] = useState(checkpoint.sounds_like.join(", "));
  return (
    <form
      className="mt-4 space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (choice !== "none") onAnswer({ choice });
        else
          onAnswer({
            choice: null,
            sounds_like: soundsLike.split(",").map((s) => s.trim()).filter(Boolean),
          });
      }}
    >
      <fieldset className="space-y-2">
        <legend className="sr-only">Artist on Qloo</legend>
        {checkpoint.candidates.map((c) => (
          <label key={c.id} className="flex cursor-pointer items-start gap-3 rounded-lg p-2 hover:bg-paper">
            <input type="radio" name="artist" value={c.id} checked={choice === c.id} onChange={() => setChoice(c.id)} className="mt-1 accent-pink" />
            <span>
              <span className="font-semibold">{c.name}</span>
              <span className="block text-sm text-ink-soft">{c.genres.slice(0, 4).join(", ") || "no genre tags"}</span>
            </span>
          </label>
        ))}
        <label className="flex cursor-pointer items-start gap-3 rounded-lg p-2 hover:bg-paper">
          <input type="radio" name="artist" value="none" checked={choice === "none"} onChange={() => setChoice("none")} className="mt-1 accent-pink" />
          <span className="font-semibold">None of these is me</span>
        </label>
      </fieldset>
      {choice === "none" && (
        <div>
          <label htmlFor="sounds-like" className="block text-sm font-semibold">
            Artists you sound like
          </label>
          <input
            id="sounds-like"
            value={soundsLike}
            onChange={(e) => setSoundsLike(e.target.value)}
            placeholder="e.g. Prateek Kuhad, Fleet Foxes (leave empty and TourScout will suggest some)"
            className="mt-1 w-full rounded-lg border border-line p-2 focus:border-ink focus:outline-none"
          />
          <p className="mt-1 text-xs text-ink-soft">We'll map their fans instead. Each name is checked on Qloo first.</p>
        </div>
      )}
      <button type="submit" className="rounded-full bg-pink px-5 py-2.5 font-semibold text-white hover:bg-pink-deep">
        {choice === "none" ? "Use these artists' fans" : "Yes, that's me"}
      </button>
    </form>
  );
}

function PickCities({ checkpoint, onAnswer }: { checkpoint: Extract<Checkpoint, { type: "pick_cities" }>; onAnswer: Answer }) {
  const [picked, setPicked] = useState<Set<string>>(new Set(checkpoint.selected));
  const toggle = (metro: string) =>
    setPicked((p) => {
      const next = new Set(p);
      if (next.has(metro)) next.delete(metro);
      else next.add(metro);
      return next;
    });
  return (
    <div className="mt-3">
      <p className="text-sm text-ink-soft">{checkpoint.question} Demand is how strongly your kind of fans over-index there; reach is how much you already reach them.</p>
      <div className="mt-3 max-h-[22rem] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-sheet text-left text-ink-soft">
            <tr>
              <th className="w-8 py-1" />
              <th className="py-1 font-medium">City</th>
              <th className="py-1 font-medium">Demand</th>
              <th className="py-1 text-right font-medium">Reach</th>
            </tr>
          </thead>
          <tbody>
            {checkpoint.metros.map((m) => (
              <tr key={m.metro} className="border-t border-line">
                <td className="py-1.5">
                  <input
                    type="checkbox"
                    aria-label={`Include ${m.metro}`}
                    checked={picked.has(m.metro)}
                    onChange={() => toggle(m.metro)}
                    className="size-4 accent-pink"
                  />
                </td>
                <td className="py-1.5">
                  <span className="font-medium">{m.metro}</span>
                  <span className="block text-xs text-ink-soft">{LABEL_TEXT[m.label]}</span>
                </td>
                <td className="py-1.5">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-24 rounded-full bg-paper" aria-hidden>
                      <div className={`h-2 rounded-full ${m.label === "unserved" ? "bg-pink" : "bg-ink"}`} style={{ width: `${m.demand}%` }} />
                    </div>
                    <span>{Math.round(m.demand)}</span>
                  </div>
                </td>
                <td className="py-1.5 text-right">{Math.round(m.reach)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        type="button"
        disabled={picked.size === 0}
        onClick={() => onAnswer({ selected: checkpoint.metros.map((m) => m.metro).filter((m) => picked.has(m)) })}
        className="mt-4 rounded-full bg-pink px-5 py-2.5 font-semibold text-white hover:bg-pink-deep disabled:opacity-40"
      >
        Plan these {picked.size} cities
      </button>
    </div>
  );
}
