import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { signInEnabled, useAccount } from "./auth";
import { AccountMenu } from "./components/AccountMenu";
import { CheckpointCard } from "./components/Checkpoints";
import { CityCard } from "./components/CityCard";
import { Compare, Outreach } from "./components/Extras";
import { MyTours } from "./components/MyTours";
import { SignIn } from "./components/SignIn";
import { StartPanel } from "./components/StartPanel";
import { TourMap } from "./components/TourMap";
import { TourPoster } from "./components/TourPoster";
import { Trace } from "./components/Trace";
import { useTour } from "./useTour";

type Tab = "tour" | "compare" | "drafts";
type View = "plan" | "sign_in" | "tours";

export function App() {
  const { run, start, answer, refine, open, reset } = useTour();
  const { state: account, signOut } = useAccount();
  const [view, setView] = useState<View>("plan");
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const claimed = useRef(false);
  const [active, setActive] = useState<number | null>(null);
  const [tab, setTab] = useState<Tab>("tour");
  const [change, setChange] = useState("");
  const working = run.phase === "running";

  useEffect(() => {
    if (run.phase === "done") setActive(0);
  }, [run.phase, run.plan]);

  // Once signed in (email, or back from Google), move this browser's guest tours into the account.
  useEffect(() => {
    if (account.status !== "signed_in" || claimed.current) return;
    claimed.current = true;
    api.claimGuestTours().then(
      (moved) => moved > 0 && setNotice(`Saved ${moved} tour${moved > 1 ? "s" : ""} from this browser to your account.`),
      () => {},
    );
  }, [account.status]);
  useEffect(() => {
    if (account.status === "guest") claimed.current = false;
  }, [account.status]);

  const goPlan = () => {
    setView("plan");
    reset();
  };

  const deleteAccount = async () => {
    try {
      const res = await (await api.deleteAccount()).json();
      await signOut();
      setConfirmDelete(false);
      goPlan();
      setNotice(
        res.login_deleted
          ? "Your account and all your tours are deleted."
          : "Your tours are deleted. Removing the login itself isn't set up on this server yet.",
      );
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Couldn't delete the account.");
    }
  };

  const plan = run.plan;
  const stop = plan && active != null ? plan.stops[active] : null;

  return (
    <div className="min-h-screen lg:grid lg:h-screen lg:grid-cols-[minmax(0,560px)_1fr]">
      <main className="flex flex-col lg:h-screen lg:overflow-y-auto">
        <header className="flex items-center justify-between px-5 pt-5 sm:px-8">
          <button type="button" onClick={goPlan} className="flex items-center gap-2" aria-label="TourScout, start over">
            <img src="/favicon.svg" alt="" className="size-7" />
            <span className="font-display text-xl font-extrabold tracking-tight">TourScout</span>
          </button>
          <div className="flex items-center gap-4">
            {view === "plan" && run.phase !== "idle" && (
              <button type="button" onClick={goPlan} className="text-sm font-semibold underline underline-offset-4">
                New plan
              </button>
            )}
            {signInEnabled && (
              <AccountMenu
                state={account}
                onSignIn={() => setView("sign_in")}
                onTours={() => setView("tours")}
                onSignOut={async () => {
                  await signOut();
                  goPlan();
                }}
                onDelete={() => setConfirmDelete(true)}
              />
            )}
          </div>
        </header>

        <div className="flex-1 space-y-6 px-5 py-6 sm:px-8">
          {notice && (
            <div role="status" className="flex items-start justify-between gap-3 rounded-2xl bg-yellow/40 p-4 text-sm font-semibold">
              <span>{notice}</span>
              <button type="button" onClick={() => setNotice(null)} aria-label="Dismiss" className="font-bold">
                ×
              </button>
            </div>
          )}

          {confirmDelete && account.status === "signed_in" && (
            <div role="alertdialog" aria-labelledby="del-title" className="rounded-2xl border-2 border-pink bg-sheet p-5">
              <p id="del-title" className="font-semibold">Delete your account?</p>
              <p className="mt-1 text-ink-soft">
                This deletes {account.account.email}, every saved tour and its drafts. It can't be undone.
              </p>
              <div className="mt-3 flex gap-3">
                <button type="button" onClick={deleteAccount} className="rounded-full bg-pink-deep px-5 py-2 font-semibold text-white">
                  Delete everything
                </button>
                <button type="button" onClick={() => setConfirmDelete(false)} className="rounded-full border-2 border-ink px-5 py-2 font-semibold">
                  Keep my account
                </button>
              </div>
            </div>
          )}

          {view === "sign_in" && account.status !== "signed_in" && (
            <SignIn onDone={() => setView("tours")} onGuest={() => setView("plan")} />
          )}

          {view === "tours" && (
            <MyTours
              signedIn={account.status === "signed_in"}
              onNew={goPlan}
              onOpen={(id) => {
                setView("plan");
                open(id);
              }}
            />
          )}

          {view === "plan" && <>
          {run.phase === "idle" && account.status === "guest" && signInEnabled && (
            <p className="text-sm text-ink-soft">
              Planning as a guest.{" "}
              <button type="button" onClick={() => setView("sign_in")} className="font-semibold text-ink underline underline-offset-4">
                Sign in
              </button>{" "}
              to keep your tours on every device.
            </p>
          )}
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
                    <button type="button" onClick={() => api.download(run.threadId!, "csv")} className="underline underline-offset-4">
                      Download as spreadsheet (CSV)
                    </button>
                    <button type="button" onClick={() => api.download(run.threadId!, "ics")} className="underline underline-offset-4">
                      Add dates to your calendar (.ics)
                    </button>
                  </div>
                </>
              )}
              {tab === "compare" && <Compare plan={plan} threadId={run.threadId} />}
              {tab === "drafts" && <Outreach plan={plan} />}
            </>
          )}
          </>}
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
