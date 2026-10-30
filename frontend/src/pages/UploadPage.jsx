import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ErrorBanner, Field, Notice } from "../components/ui.jsx";
import { uploadPhoto } from "../lib/api.js";

const ALLOWED = ["image/jpeg", "image/png", "image/webp"];
const MAX = 5 * 1024 * 1024;

export function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [caption, setCaption] = useState("");
  const [visibility, setVisibility] = useState("friends");
  const [tags, setTags] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function choose(event) {
    const selected = event.target.files?.[0] ?? null;
    setError("");
    if (!selected) {
      setFile(null);
      return;
    }
    if (!ALLOWED.includes(selected.type)) {
      setError("Choose a JPEG, PNG or WebP image.");
      setFile(null);
      return;
    }
    if (selected.size > MAX) {
      setError("The image must be 5 MB or smaller.");
      setFile(null);
      return;
    }
    setFile(selected);
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!file) {
      setError("Choose an image first.");
      return;
    }
    setBusy(true);
    try {
      const photo = await uploadPhoto({ file, caption: caption.trim(), visibility, tags: tags.trim() });
      navigate(`/photos/${photo.id}`);
    } catch (problem) {
      setError(problem.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="narrow card">
      <h1>Upload a photo</h1>
      <p className="lede">JPEG, PNG or WebP, up to 5 MB. You can upload 20 photos a day.</p>

      <ErrorBanner message={error} />

      <form onSubmit={submit}>
        <Field id="file" label="Image" hint="The server checks the file type and size again.">
          <input id="file" type="file" accept="image/jpeg,image/png,image/webp" onChange={choose} />
        </Field>

        <Field id="caption" label="Caption" hint="Optional, up to 1000 characters.">
          <textarea
            id="caption"
            value={caption}
            maxLength={1000}
            onChange={(event) => setCaption(event.target.value)}
          />
        </Field>

        <fieldset className="field">
          <legend>
            <strong>Who can see this photo?</strong>
          </legend>
          <label className="row" style={{ fontWeight: 400 }}>
            <input
              type="radio"
              name="visibility"
              value="friends"
              checked={visibility === "friends"}
              onChange={() => setVisibility("friends")}
              style={{ width: "auto" }}
            />
            My accepted friends
          </label>
          <label className="row" style={{ fontWeight: 400 }}>
            <input
              type="radio"
              name="visibility"
              value="owner"
              checked={visibility === "owner"}
              onChange={() => setVisibility("owner")}
              style={{ width: "auto" }}
            />
            Only me
          </label>
        </fieldset>

        <Field id="tags" label="Tags" hint="Comma separated, for example: sunset, lake">
          <input id="tags" value={tags} onChange={(event) => setTags(event.target.value)} />
        </Field>

        <button className="button" type="submit" disabled={busy}>
          {busy ? "Uploading" : "Upload"}
        </button>
      </form>
    </div>
  );
}
