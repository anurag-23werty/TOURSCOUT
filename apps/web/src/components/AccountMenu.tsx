import { useEffect, useRef, useState } from "react";
import type { AccountState } from "../auth";

/** Header corner: "Sign in" for guests, an initial with a small menu once signed in. */
export function AccountMenu(props: {
  state: AccountState;
  onSignIn: () => void;
  onTours: () => void;
  onSignOut: () => void;
  onDelete: () => void;
}) {
  const { state } = props;
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  if (state.status === "loading") return <span className="size-9" aria-hidden="true" />;

  if (state.status === "guest")
    return (
      <div className="flex items-center gap-4 text-sm font-semibold">
        <button type="button" onClick={props.onTours} className="underline underline-offset-4">
          My tours
        </button>
        <button type="button" onClick={props.onSignIn} className="rounded-full border-2 border-ink px-4 py-1.5">
          Sign in
        </button>
      </div>
    );

  const { account } = state;
  const item = "block w-full rounded-lg px-3 py-2 text-left hover:bg-paper";
  const pick = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`Account: ${account.email}`}
        className="grid size-9 place-items-center overflow-hidden rounded-full bg-ink font-display font-bold text-white"
      >
        {account.image ? <img src={account.image} alt="" className="size-full object-cover" /> : (account.name || account.email)[0]?.toUpperCase()}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-[1000] mt-2 w-60 rounded-2xl border border-line bg-sheet p-2 text-sm shadow-lg">
          <p className="px-3 py-2">
            <span className="block font-semibold">{account.name || "Signed in"}</span>
            <span className="block truncate text-ink-soft">{account.email}</span>
          </p>
          <button type="button" role="menuitem" className={item} onClick={pick(props.onTours)}>
            My tours
          </button>
          <button type="button" role="menuitem" className={item} onClick={pick(props.onSignOut)}>
            Sign out
          </button>
          <button type="button" role="menuitem" className={`${item} text-pink-deep`} onClick={pick(props.onDelete)}>
            Delete account…
          </button>
        </div>
      )}
    </div>
  );
}
