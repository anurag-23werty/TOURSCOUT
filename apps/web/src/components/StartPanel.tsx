import { useEffect, useState } from "react";
import { api } from "../api";
import type { Persona } from "../types";

interface Props {
  busy: boolean;
  onStart: (body: { message?: string; persona_id?: string; upload_id?: string; auto_approve: boolean }) => void;
}

const EXAMPLE = "I'm Hovvdy, an indie band from Austin. 8 shows in the Midwest in April, about 400 people a night.";

export function StartPanel({ busy, onStart }: Props) {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [message, setMessage] = useState("");
  const [askMe, setAskMe] = useState(true);
  const [upload, setUpload] = useState<{ id: string; summary: string } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    api.personas().then((rows) => setPersonas(rows.filter((p) => p.featured))).catch(() => setPersonas([]));
  }, []);

  async function onFile(file: File | undefined) {
    setUpload(null);
    setUploadError(null);
    if (!file) return;
    try {
      const res = await api.upload(file);
      const summary =
        res.preview.kind === "csv"
          ? `${res.preview.total_rows} cities from ${file.name}`
          : `Screenshot ${file.name}: cities are read when the plan starts`;
      setUpload({ id: res.upload_id, summary });
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
    }
  }

  const canPlan = !busy && message.trim().length >= 10;

  return (
    <section aria-labelledby="start-title" className="space-y-6">
      <div>
        <h1 id="start-title" className="poster-type text-[clamp(2.6rem,5vw,4rem)] text-ink">
          Find the cities that are waiting for you.
        </h1>
        <p className="mt-3 max-w-[52ch] text-ink-soft">
          TourScout maps where people with your fans' taste live, compares it with where you already have listeners, and
          builds a routed tour with real venues, local openers and brands your fans love.
        </p>
      </div>

      {personas.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-semibold">Try a demo artist</p>
          <div className="flex flex-wrap gap-2">
            {personas.map((p) => (
              <button
                key={p.id}
                type="button"
                disabled={busy}
                onClick={() => onStart({ persona_id: p.id, auto_approve: !askMe })}
                className="rounded-full border border-ink/25 bg-sheet px-4 py-2 text-left text-sm hover:border-ink disabled:opacity-50"
              >
                <span className="font-semibold">{p.artist}</span>
                <span className="text-ink-soft">
                  {" "}
                  {p.n_shows} shows, {p.regions.join(", ").replace("US ", "")}
                  {p.sounds_like.length > 0 && " (not on Qloo)"}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <form
        className="space-y-3 rounded-2xl bg-sheet p-4 shadow-[0_1px_0_var(--color-line)]"
        onSubmit={(e) => {
          e.preventDefault();
          if (canPlan) onStart({ message: message.trim(), upload_id: upload?.id, auto_approve: !askMe });
        }}
      >
        <label htmlFor="request" className="block text-sm font-semibold">
          Or describe your tour
        </label>
        <textarea
          id="request"
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={EXAMPLE}
          className="w-full resize-y rounded-lg border border-line bg-paper/60 p-3 text-[15px] placeholder:text-mid focus:border-ink focus:outline-none"
        />

        <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
          <label className="flex cursor-pointer items-center gap-2">
            <input type="checkbox" checked={askMe} onChange={(e) => setAskMe(e.target.checked)} className="size-4 accent-pink" />
            Let me confirm the artist and cities
          </label>
          <label className="cursor-pointer text-ink-soft underline decoration-line underline-offset-4 hover:text-ink">
            Add your top cities (CSV or a streaming-dashboard screenshot)
            <input
              type="file"
              accept=".csv,image/png,image/jpeg,image/webp"
              className="sr-only"
              onChange={(e) => onFile(e.target.files?.[0])}
            />
          </label>
        </div>
        {upload && <p className="text-sm text-ink-soft">Added: {upload.summary}</p>}
        {uploadError && (
          <p role="alert" className="text-sm text-pink-deep">
            {uploadError}
          </p>
        )}

        <button
          type="submit"
          disabled={!canPlan}
          className="rounded-full bg-pink px-6 py-3 font-semibold text-white hover:bg-pink-deep disabled:cursor-not-allowed disabled:opacity-40"
        >
          Plan my tour
        </button>
      </form>
      <p className="text-xs text-ink-soft">
        Your uploads stay in memory and are deleted once the plan reads them. Taste data from Qloo; hometowns from
        MusicBrainz; cities from GeoNames.
      </p>
    </section>
  );
}
