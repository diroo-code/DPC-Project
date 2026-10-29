import { useEffect, useState } from "react";

import { ErrorBanner, Field, Spinner } from "../components/ui.jsx";
import { updateMe } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";

export function ProfilePage() {
  const { profile, setProfile } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (profile) {
      setDisplayName(profile.display_name ?? "");
      setBio(profile.bio ?? "");
    }
  }, [profile]);

  if (!profile) return <Spinner label="Loading your profile" />;

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSaved(false);
    setBusy(true);
    try {
      const updated = await updateMe({ display_name: displayName.trim(), bio: bio.trim() || null });
      setProfile(updated);
      setSaved(true);
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="narrow card">
      <h1>Your profile</h1>
      <p className="lede">
        @{profile.username} · joined {new Date(profile.created_at).toLocaleDateString()}
      </p>

      <ErrorBanner message={error} />
      {saved && <p className="banner banner-notice">Profile saved.</p>}

      <form onSubmit={submit}>
        <Field id="display_name" label="Display name" hint="Up to 80 characters.">
          <input
            id="display_name"
            value={displayName}
            maxLength={80}
            required
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </Field>
        <Field id="bio" label="About you" hint="Optional, up to 500 characters.">
          <textarea
            id="bio"
            value={bio}
            maxLength={500}
            onChange={(event) => setBio(event.target.value)}
          />
        </Field>
        <button className="button" type="submit" disabled={busy}>
          {busy ? "Saving" : "Save changes"}
        </button>
      </form>

      <p className="hint" style={{ marginTop: "1rem" }}>
        Usernames cannot be changed here. Your email is never shown to other users.
      </p>
    </div>
  );
}
