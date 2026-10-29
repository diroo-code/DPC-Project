import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { getMe, setTokenProvider } from "./api.js";
import { supabase, supabaseEnabled } from "./supabase.js";

const AuthContext = createContext(null);

const DEV_TOKEN_KEY = "dev_access_token";

function fromSupabaseSession(session) {
  if (!session) return { status: "signed_out", token: null, email: null, userId: null };
  return {
    status: "signed_in",
    token: session.access_token,
    email: session.user?.email ?? null,
    userId: session.user?.id ?? null,
  };
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState({ status: "loading", token: null, email: null, userId: null });
  const [profile, setProfile] = useState(null);

  // Set synchronously during render, not in an effect. Child effects run before parent effects, so
  // installing the token in an effect left the first data request (the feed, an upload) unauthenticated.
  setTokenProvider(() => session.token);

  useEffect(() => {
    if (supabase) {
      supabase.auth.getSession().then(({ data }) => setSession(fromSupabaseSession(data.session)));
      const { data } = supabase.auth.onAuthStateChange((_event, next) =>
        setSession(fromSupabaseSession(next)),
      );
      return () => data.subscription.unsubscribe();
    }

    const stored = sessionStorage.getItem(DEV_TOKEN_KEY);
    setSession({
      status: stored ? "signed_in" : "signed_out",
      token: stored,
      email: null,
      userId: null,
    });
    return undefined;
  }, []);

  // Load the profile whenever the token changes. A 401 clears the session.
  useEffect(() => {
    if (session.status !== "signed_in" || !session.token) {
      setProfile(null);
      return;
    }
    let cancelled = false;
    getMe()
      .then((data) => {
        if (!cancelled) setProfile(data);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error.status === 401) {
          sessionStorage.removeItem(DEV_TOKEN_KEY);
          setSession({ status: "signed_out", token: null, email: null, userId: null });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [session.status, session.token]);

  const signIn = useCallback(async (email, password) => {
    if (!supabase) throw new Error("Supabase is not configured.");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
  }, []);

  const signUp = useCallback(async (email, password, username, displayName) => {
    if (!supabase) throw new Error("Supabase is not configured.");
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { username, display_name: displayName } },
    });
    if (error) throw new Error(error.message);
  }, []);

  const signOut = useCallback(async () => {
    if (supabase) await supabase.auth.signOut();
    sessionStorage.removeItem(DEV_TOKEN_KEY);
    setSession({ status: "signed_out", token: null, email: null, userId: null });
    setProfile(null);
  }, []);

  // Development only: a token issued locally by the test or live-check script.
  const useDevToken = useCallback(async (token) => {
    sessionStorage.setItem(DEV_TOKEN_KEY, token);
    setSession({ status: "signed_in", token, email: null, userId: null });
    try {
      await getMe();
    } catch (error) {
      sessionStorage.removeItem(DEV_TOKEN_KEY);
      setSession({ status: "signed_out", token: null, email: null, userId: null });
      throw error;
    }
  }, []);

  const value = useMemo(
    () => ({
      ...session,
      profile,
      setProfile,
      signIn,
      signUp,
      signOut,
      useDevToken,
      supabaseEnabled,
      devAuthAvailable: !supabaseEnabled && import.meta.env.VITE_DEV_AUTH === "1",
    }),
    [session, profile, signIn, signUp, signOut, useDevToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
