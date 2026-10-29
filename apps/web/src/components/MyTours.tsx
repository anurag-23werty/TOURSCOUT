import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { MyPlan } from "../types";

const when = (s: number) => new Date(s * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

/** Saved tours: reopen, rename, delete. Signed-in users see them on every device; guests see this browser's. */
export function MyTours({ signedIn, onOpen, onNew }: { signedIn: boolean; onOpen: (threadId: string) => void; onNew: () => void }) {
  const [rows, setRows] = useState<MyPlan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);

  const load = useCallback(() => {
    api.myPlans().then(setRows, (e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  const rename = async (id: string) => {
    await api.rename(id, title.trim());
    setEditing(null);
    load();
  };

  const remove = async (id: string) => {
    await api.remove(id);
    setConfirming(null);
    setRows((r) => r?.filter((p) => p.thread_id !== id) ?? null);
  };

  return (
    <section aria-labelledby="tours-title" className="space-y-4">
      <div className="flex items-end justify-between gap-4">
        <h1 id="tours-title" className="font-display text-3xl font-extrabold tracking-tight">
          My tours
        </h1>
        <button type="button" onClick={onNew} className="rounded-full bg-pink px-4 py-2 text-sm font-semibold text-white">
          Plan a new tour
        </button>
      </div>
      {!signedIn && <p className="text-sm text-ink-soft">These are the tours from this browser. Sign in to keep them on every device.</p>}

      {error && (
        <p role="alert" className="rounded-2xl border-2 border-pink bg-sheet p-4">
          Couldn't load your tours: {error}
        </p>
      )}
      {rows === null && !error && <p className="text-ink-soft">Loading…</p>}
      {rows?.length === 0 && (
        <div className="rounded-2xl bg-sheet p-6">
          <p className="font-semibold">No tours yet.</p>
          <p className="mt-1 text-ink-soft">Plan one and it shows up here.</p>
        </div>
      )}

      <ul className="space-y-2">
        {rows?.map((p) => {
          const name = p.title || p.headline || (p.artist ? `${p.artist} tour` : "Unfinished tour");
          return (
            <li key={p.thread_id} className="rounded-2xl bg-sheet p-4">
              {editing === p.thread_id ? (
                <form
                  className="flex gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    rename(p.thread_id);
                  }}
                >
                  <label htmlFor={`t-${p.thread_id}`} className="sr-only">
                    Tour name
                  </label>
                  <input
                    id={`t-${p.thread_id}`}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    maxLength={120}
                    autoFocus
                    className="min-w-0 flex-1 rounded-lg border border-line p-2 focus:border-ink focus:outline-none"
                  />
                  <button type="submit" className="rounded-full bg-ink px-4 text-sm font-semibold text-white">
                    Save
                  </button>
                  <button type="button" onClick={() => setEditing(null)} className="text-sm font-semibold underline">
                    Cancel
                  </button>
                </form>
              ) : (
                <>
                  <button type="button" onClick={() => onOpen(p.thread_id)} className="block text-left">
                    <span className="font-display text-lg font-bold leading-tight">{name}</span>
                    <span className="mt-0.5 block text-sm text-ink-soft">
                      {[p.artist, `planned ${when(p.created)}`].filter(Boolean).join(", ")}
                    </span>
                  </button>
                  <div className="mt-3 flex gap-4 text-sm font-semibold">
                    <button type="button" onClick={() => onOpen(p.thread_id)} className="underline underline-offset-4">
                      Open
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditing(p.thread_id);
                        setTitle(name);
                      }}
                      className="underline underline-offset-4"
                    >
                      Rename
                    </button>
                    {confirming === p.thread_id ? (
                      <span className="flex gap-3">
                        <button type="button" onClick={() => remove(p.thread_id)} className="text-pink-deep underline underline-offset-4">
                          Yes, delete it
                        </button>
                        <button type="button" onClick={() => setConfirming(null)} className="underline underline-offset-4">
                          Keep
                        </button>
                      </span>
                    ) : (
                      <button type="button" onClick={() => setConfirming(p.thread_id)} className="underline underline-offset-4">
                        Delete
                      </button>
                    )}
                  </div>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
