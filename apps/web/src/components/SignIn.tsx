import { useState } from "react";
import { signInWithEmail, signInWithGoogle, signUpWithEmail } from "../auth";

type Mode = "sign_in" | "sign_up";

/** Sign in or create an account; "Continue as guest" is always one click away. */
export function SignIn({ onDone, onGuest }: { onDone: () => void; onGuest: () => void }) {
  const [mode, setMode] = useState<Mode>("sign_in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const err =
      mode === "sign_in" ? await signInWithEmail(email.trim(), password) : await signUpWithEmail(name.trim(), email.trim(), password);
    setBusy(false);
    if (err) setError(err);
    else onDone();
  };

  const google = async () => {
    setBusy(true);
    setError(null);
    const err = await signInWithGoogle(); // on success the page navigates to Google
    if (err) {
      setBusy(false);
      setError(err);
    }
  };

  return (
    <section aria-labelledby="signin-title" className="mx-auto max-w-sm space-y-5">
      <div>
        <h1 id="signin-title" className="font-display text-3xl font-extrabold tracking-tight">
          {mode === "sign_in" ? "Sign in to TourScout" : "Create your account"}
        </h1>
        <p className="mt-2 text-ink-soft">Keep your tours, reopen them on any device, and plan more each hour.</p>
      </div>

      <button
        type="button"
        onClick={google}
        disabled={busy}
        className="flex w-full items-center justify-center gap-3 rounded-full border-2 border-ink bg-sheet px-5 py-3 font-semibold disabled:opacity-50"
      >
        <svg viewBox="0 0 24 24" className="size-5" aria-hidden="true">
          <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.4h6.5a5.6 5.6 0 0 1-2.4 3.6v3h3.9c2.3-2.1 3.5-5.2 3.5-8.7z" />
          <path fill="#34A853" d="M12 24c3.2 0 6-1.1 7.9-2.9l-3.9-3c-1 .7-2.4 1.1-4 1.1-3.1 0-5.7-2.1-6.7-4.9h-4v3.1A12 12 0 0 0 12 24z" />
          <path fill="#FBBC05" d="M5.3 14.3a7.2 7.2 0 0 1 0-4.6V6.6h-4a12 12 0 0 0 0 10.8l4-3.1z" />
          <path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4A12 12 0 0 0 1.3 6.6l4 3.1C6.3 6.9 8.9 4.8 12 4.8z" />
        </svg>
        Continue with Google
      </button>

      <div className="flex items-center gap-3 text-sm text-mid" aria-hidden="true">
        <span className="h-px flex-1 bg-line" /> or with email <span className="h-px flex-1 bg-line" />
      </div>

      <form onSubmit={submit} className="space-y-3">
        {mode === "sign_up" && (
          <Field label="Your name or band name" id="name" value={name} onChange={setName} autoComplete="name" required />
        )}
        <Field label="Email" id="email" type="email" value={email} onChange={setEmail} autoComplete="email" required />
        <Field
          label="Password"
          id="password"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete={mode === "sign_in" ? "current-password" : "new-password"}
          minLength={8}
          hint={mode === "sign_up" ? "At least 8 characters." : undefined}
          required
        />
        {error && (
          <p role="alert" className="rounded-lg bg-pink/10 p-3 text-sm font-semibold text-pink-deep">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy} className="w-full rounded-full bg-pink px-5 py-3 font-semibold text-white disabled:opacity-50">
          {busy ? "One moment…" : mode === "sign_in" ? "Sign in" : "Create account"}
        </button>
      </form>

      <p className="text-sm">
        {mode === "sign_in" ? "New to TourScout? " : "Already have an account? "}
        <button
          type="button"
          className="font-semibold underline underline-offset-4"
          onClick={() => {
            setMode(mode === "sign_in" ? "sign_up" : "sign_in");
            setError(null);
          }}
        >
          {mode === "sign_in" ? "Create an account" : "Sign in"}
        </button>
      </p>

      <div className="border-t border-line pt-4">
        <button type="button" onClick={onGuest} className="font-semibold underline underline-offset-4">
          Continue as a guest
        </button>
        <p className="mt-1 text-sm text-ink-soft">Guest tours stay in this browser. Sign in later to keep them.</p>
      </div>
    </section>
  );
}

function Field(props: {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  autoComplete?: string;
  required?: boolean;
  minLength?: number;
  hint?: string;
}) {
  const { label, id, value, onChange, hint, ...rest } = props;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-semibold">
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="mt-1 w-full rounded-lg border border-line bg-sheet p-2.5 focus:border-ink focus:outline-none"
        {...rest}
      />
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-ink-soft">
          {hint}
        </p>
      )}
    </div>
  );
}
