// Sign-in with Neon Auth (managed Better Auth). Optional: without VITE_NEON_AUTH_URL the app is guests-only.
//
// The browser talks to Neon Auth directly (its session cookie is SameSite=None; Partitioned). Our API never sees that
// cookie: it gets a 15-minute JWT from authClient.token(), sent as `Authorization: Bearer`.

import { createAuthClient } from "@neondatabase/auth";
import { useCallback, useEffect, useState } from "react";

const AUTH_URL = (import.meta.env.VITE_NEON_AUTH_URL as string | undefined)?.replace(/\/$/, "") ?? "";

// Better Auth sends `credentials: "include"` by default, so the Neon session cookie goes along on cross-site calls.
export const authClient = AUTH_URL ? createAuthClient(AUTH_URL) : null;
export const signInEnabled = authClient !== null;

export interface Account {
  id: string;
  email: string;
  name: string;
  image: string | null;
}

// ---------------------------------------------------------------- tokens for our API

let cached: { token: string; exp: number } | null = null;

/** JWT `exp` in ms. Exported for tests. */
export function jwtExpiry(token: string): number {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" ? payload.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

/** A valid access token for the API, or null for guests. Refreshed a minute before it expires. */
export async function apiToken(): Promise<string | null> {
  if (!authClient || !signedIn) return null;
  if (cached && cached.exp - Date.now() > 60_000) return cached.token;
  const { data } = await authClient.token();
  const token = data?.token ?? null;
  cached = token ? { token, exp: jwtExpiry(token) } : null;
  if (!token) setSignedIn(false); // the Neon session ended (signed out in another tab, or expired)
  return token;
}

export function forgetToken() {
  cached = null;
}

// ---------------------------------------------------------------- who is signed in

let signedIn = false;
const listeners = new Set<(a: Account | null) => void>();
let current: Account | null = null;

function setSignedIn(value: boolean, account: Account | null = null) {
  signedIn = value;
  current = value ? account : null;
  if (!value) cached = null;
  listeners.forEach((l) => l(current));
}

export async function loadAccount(): Promise<Account | null> {
  if (!authClient) return null;
  const { data } = await authClient.getSession();
  const u = data?.user;
  setSignedIn(Boolean(u), u ? { id: u.id, email: u.email, name: u.name, image: u.image ?? null } : null);
  return current;
}

export type AccountState = { status: "loading" } | { status: "guest" } | { status: "signed_in"; account: Account };

export function useAccount() {
  const [state, setState] = useState<AccountState>(signInEnabled ? { status: "loading" } : { status: "guest" });

  useEffect(() => {
    const listener = (a: Account | null) => setState(a ? { status: "signed_in", account: a } : { status: "guest" });
    listeners.add(listener);
    if (signInEnabled) loadAccount().catch(() => setState({ status: "guest" }));
    return () => {
      listeners.delete(listener);
    };
  }, []);

  const signOut = useCallback(async () => {
    await authClient?.signOut();
    setSignedIn(false);
  }, []);

  return { state, signOut, refresh: loadAccount };
}

// ---------------------------------------------------------------- sign-in actions (errors come back as text)

const message = (e: { message?: string; status?: number } | null | undefined, fallback: string) =>
  e?.message || fallback;

export async function signInWithEmail(email: string, password: string): Promise<string | null> {
  const { error } = await authClient!.signIn.email({ email, password });
  if (error) return error.status === 401 ? "That email and password don't match." : message(error, "Couldn't sign in.");
  await loadAccount();
  return null;
}

export async function signUpWithEmail(name: string, email: string, password: string): Promise<string | null> {
  const { error } = await authClient!.signUp.email({ name, email, password });
  if (error) return message(error, "Couldn't create the account.");
  await loadAccount();
  return null;
}

export async function signInWithGoogle(): Promise<string | null> {
  // Full-page redirect to Google; Neon Auth brings the browser back here with a one-time session verifier.
  const { error } = await authClient!.signIn.social({ provider: "google", callbackURL: window.location.origin + "/" });
  return error ? message(error, "Couldn't start Google sign-in.") : null;
}
