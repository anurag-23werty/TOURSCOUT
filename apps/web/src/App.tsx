import { useEffect, useState } from "react";
import { api } from "./api";
import { CheckpointCard } from "./components/Checkpoints";
import { CityCard } from "./components/CityCard";
import { Compare, Outreach } from "./components/Extras";
import { StartPanel } from "./components/StartPanel";
import { TourMap } from "./components/TourMap";
import { TourPoster } from "./components/TourPoster";
import { Trace } from "./components/Trace";
import { useTour } from "./useTour";

type Tab = "tour" | "compare" | "drafts";

export function App() {
  const { run, start, answer, refine, reset } = useTour();
  const [active, setActive] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("tour");
  const [change, setChange] = useState("");
  const working = run.phase === "running";

  useEffect(() => {
    if (run.phase === "done") setActive(0);
  }, [run.phase, run.plan]);

  const plan = run.plan;
  const stop = plan && active != null ? plan.stops[active] : null;

  return (
    <div className="min-h-screen lg:grid lg:h-screen lg:grid-cols-[minmax(0,560px)_1fr]">
      <main className="flex flex-col lg:h-screen lg:overflow-y-auto">
        <header className="flex items-center justify-between px-5 pt-5 sm:px-8">
          <button type="button" onClick={reset} className="flex items-center gap-2" aria-label="TourScout, start over">
            <img src="/favicon.svg" alt="" className="size-7" />
            <span className="font-display text-xl font-extrabold tracking-tight">TourScout</span>
          </button>
          {run.phase !== "idle" && (
            <button type="button" onClick={reset} className="text-sm font-semibold underline underline-offset-4">
              New plan
            </button>
          )}
        </header>

        <div className="flex-1 space-y-6 px-5 py-6 sm:px-8">
          {run.phase === "idle" && <StartPanel busy={working} onStart={start} />}

          {run.phase !== "idle" && !plan && <Trace steps={run.steps} working={working} />}

          {run.phase === "waiting" && run.checkpoint && <CheckpointCard checkpoint={run.checkpoint} onAnswer={answer} />}

          {run.phase === "error" && (
            <div role="alert" className="rounded-2xl border-2 border-pink bg-sheet p-5">
              <p className="font-semibold">The plan stopped.</p>
              <p className="mt-1 text-ink-soft">{run.error}</p>
              <button type="button" onClick={reset} className="mt-3 rounded-full bg-ink px-5 py-2 font-semibold text-white">
                Start again
              </button>
            </div>
          )}

          {plan && run.threadId && (
            <>
              <nav aria-label="Plan views" className="flex gap-1 rounded-full bg-sheet p-1 text-sm font-semibold">
                {(
                  [
                    ["tour", "Tour"],
                    ["compare", "Compare"],
                    ["drafts", "Drafts"],
                  ] as [Tab, string][]
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setTab(id)}
                    aria-current={tab === id ? "page" : undefined}
                    className={`flex-1 rounded-full px-3 py-2 ${tab === id ? "bg-ink text-white" : "hover:bg-paper"}`}
                  >
                    {label}
                  </button>
                ))}
              </nav>

              {tab === "tour" && (
                <>
                  <TourPoster plan={plan} active={active} onSelect={setActive} />
                  <div className="lg:hidden">
                    <div className="h-[55vh] overflow-hidden rounded-2xl">
                      <TourMap metros={run.metros} stops={plan.stops} active={active} onSelect={setActive} />
                    </div>
                  </div>
                  {stop && <CityCard key={stop.metro + stop.date} stop={stop} threadId={run.threadId} />}

                  <form
                    className="rounded-2xl bg-sheet p-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (change.trim().length > 2) refine(change.trim()).then(() => setChange(""));
                    }}
                  >
                    <label htmlFor="refine" className="block text-sm font-semibold">
                      Change something
                    </label>
                    <div className="mt-2 flex gap-2">
                      <input
                        id="refine"
                        value={change}
                        onChange={(e) => setChange(e.target.value)}
                        placeholder="Skip Detroit, only 6 shows, max 400 km a day"
                        disabled={working}
                        className="min-w-0 flex-1 rounded-lg border border-line p-2 focus:border-ink focus:outline-none"
                      />
                      <button type="submit" disabled={working || change.trim().length < 3} className="rounded-full bg-pink px-4 font-semibold text-white disabled:opacity-40">
                        {working ? "Updating…" : "Update plan"}
                      </button>
                    </div>
                    {working && <Trace steps={run.steps.slice(-6)} working />}
                  </form>

                  <div className="flex flex-wrap gap-4 text-sm font-semibold">
                    <a href={api.exportUrl(run.threadId, "csv")} className="underline underline-offset-4">
                      Download as spreadsheet (CSV)
                    </a>
                    <a href={api.exportUrl(run.threadId, "ics")} className="underline underline-offset-4">
                      Add dates to your calendar (.ics)
                    </a>
                  </div>
                </>
              )}
              {tab === "compare" && <Compare plan={plan} threadId={run.threadId} />}
              {tab === "drafts" && <Outreach plan={plan} />}
            </>
          )}
        </div>
      </main>

      <aside className="hidden lg:block" aria-label="Map">
        {run.phase === "idle" && run.metros.length === 0 ? (
          <div className="relative h-full">
            <TourMap metros={[]} stops={[]} active={null} onSelect={() => {}} />
            <p className="pointer-events-none absolute inset-x-0 bottom-8 z-[500] mx-auto w-fit rounded-full bg-sheet px-4 py-2 text-sm shadow">
              Your fans' demand map appears here.
            </p>
          </div>
        ) : (
          <TourMap metros={run.metros} stops={plan?.stops ?? []} active={active} onSelect={setActive} />
        )}
      </aside>
    </div>
  );
}
