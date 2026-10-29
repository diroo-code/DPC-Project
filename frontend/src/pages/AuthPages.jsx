import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ErrorBanner, Field, Notice } from "../components/ui.jsx";
import { useAuth } from "../lib/auth.jsx";

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const destination = location.state?.from || "/";

  async function submitPassword(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await auth.signIn(email.trim(), password);
      navigate(destination, { replace: true });
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitToken(event) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await auth.useDevToken(token.trim());
      navigate(destination, { replace: true });
    } catch (problem) {
      setError(problem.status === 401 ? "That token was rejected." : problem.message);
    } finally {
      setBusy(false);
    }
  }

  if (auth.status === "signed_in") {
    return (
      <div className="narrow card">
        <h1>Already signed in</h1>
        <p className="lede">You can go straight to the feed.</p>
        <Link className="button" to="/">
          Open the feed
        </Link>
      </div>
    );
  }

  return (
    <div className="narrow card">
      <h1>Sign in</h1>
      <p className="lede">Use your account to see photos shared with you.</p>

      <ErrorBanner message={error} />

      {auth.supabaseEnabled && (
        <form onSubmit={submitPassword}>
          <Field id="email" label="Email">
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </Field>
          <Field id="password" label="Password">
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          <button className="button" type="submit" disabled={busy}>
            {busy ? "Signing in" : "Sign in"}
          </button>
        </form>
      )}

      {!auth.supabaseEnabled && auth.devAuthAvailable && (
        <form onSubmit={submitToken}>
          <Notice>
            Supabase is not configured in this build, so email sign-in is unavailable. Paste a token
            issued by the local backend script to use the application against the local API. Real
            authentication is blocked until a Supabase project exists.
          </Notice>
          <Field
            id="devtoken"
            label="Development access token"
            hint="Stored in this tab's session only. Never sent anywhere except the API."
          >
            <textarea
              id="devtoken"
              required
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
          </Field>
          <button className="button" type="submit" disabled={busy}>
            {busy ? "Checking" : "Use this token"}
          </button>
        </form>
      )}

      {!auth.supabaseEnabled && !auth.devAuthAvailable && (
        <Notice>
          Authentication is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY, or set
          VITE_DEV_AUTH=1 for local development. Until then, signing in is not available.
        </Notice>
      )}

      <p className="auth-switch">
        No account? <Link to="/register">Register</Link>
      </p>
    </div>
  );
}

export function RegisterPage() {
  const auth = useAuth();
  const [form, setForm] = useState({
    email: "",
    password: "",
    username: "",
    displayName: "",
  });
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  function update(field) {
    return (event) => setForm({ ...form, [field]: event.target.value });
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!/^[a-z0-9_]{3,30}$/.test(form.username)) {
      setError("Username must be 3 to 30 characters: lower case letters, digits or underscore.");
      return;
    }
    setBusy(true);
    try {
      await auth.signUp(form.email.trim(), form.password, form.username, form.displayName);
      setDone(true);
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  if (!auth.supabaseEnabled) {
    return (
      <div className="narrow card">
        <h1>Register</h1>
        <Notice>
          Registration requires Supabase Auth, which is not configured in this build. This is a
          blocked feature, not a working one. Set the Supabase environment variables to enable it.
        </Notice>
        <p className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    );
  }

  if (done) {
    return (
      <div className="narrow card">
        <h1>Check your email</h1>
        <p className="lede">
          Supabase sent a confirmation link to {form.email}. Confirm it, then sign in.
        </p>
        <Link className="button" to="/login">
          Go to sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="narrow card">
      <h1>Create an account</h1>
      <p className="lede">Your username is how friends will find you.</p>
      <ErrorBanner message={error} />
      <form onSubmit={submit}>
        <Field id="reg-username" label="Username" hint="Lower case letters, digits, underscore.">
          <input
            id="reg-username"
            required
            value={form.username}
            onChange={update("username")}
            autoComplete="username"
          />
        </Field>
        <Field id="reg-name" label="Display name">
          <input id="reg-name" required value={form.displayName} onChange={update("displayName")} />
        </Field>
        <Field id="reg-email" label="Email">
          <input
            id="reg-email"
            type="email"
            required
            value={form.email}
            onChange={update("email")}
            autoComplete="email"
          />
        </Field>
        <Field id="reg-password" label="Password" hint="At least 8 characters.">
          <input
            id="reg-password"
            type="password"
            required
            minLength={8}
            value={form.password}
            onChange={update("password")}
            autoComplete="new-password"
          />
        </Field>
        <button className="button" type="submit" disabled={busy}>
          {busy ? "Creating account" : "Create account"}
        </button>
      </form>
      <p className="auth-switch">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </div>
  );
}
