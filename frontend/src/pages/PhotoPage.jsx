import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ConfirmButton, ErrorBanner, Field, Spinner } from "../components/ui.jsx";
import { addComment, deleteComment, deletePhoto, getPhoto, listComments, mediaUrl, photoUrl } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";

export function PhotoPage() {
  const { photoId } = useParams();
  const navigate = useNavigate();
  const { profile } = useAuth();

  const [photo, setPhoto] = useState(null);
  const [src, setSrc] = useState(null);
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [body, setBody] = useState("");
  const [commentError, setCommentError] = useState("");
  const [posting, setPosting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [detail, commentsList] = await Promise.all([
        getPhoto(photoId),
        listComments(photoId),
      ]);
      setPhoto(detail);
      setComments(commentsList);
      try {
        const signed = await photoUrl(photoId);
        setSrc(mediaUrl(signed.url));
      } catch {
        setSrc(null);
      }
    } catch (problem) {
      setError(problem.status === 404 ? "This photo is not available to you." : problem.message);
    } finally {
      setLoading(false);
    }
  }, [photoId]);

  useEffect(() => {
    load();
  }, [load]);

  async function submitComment(event) {
    event.preventDefault();
    setCommentError("");
    if (!body.trim()) {
      setCommentError("Write something first.");
      return;
    }
    setPosting(true);
    try {
      const created = await addComment(photoId, body.trim());
      setComments((previous) => [...previous, created]);
      setBody("");
    } catch (problem) {
      setCommentError(problem.message);
    } finally {
      setPosting(false);
    }
  }

  async function removeComment(id) {
    setCommentError("");
    try {
      await deleteComment(id);
      setComments((previous) => previous.filter((comment) => comment.id !== id));
    } catch (problem) {
      setCommentError(problem.message);
    }
  }

  async function removePhoto() {
    try {
      await deletePhoto(photoId);
      navigate("/", { replace: true });
    } catch (problem) {
      setError(problem.message);
    }
  }

  if (loading) return <Spinner label="Loading photo" />;

  if (error || !photo) {
    return (
      <div className="card">
        <ErrorBanner message={error || "Photo not found"} onRetry={load} />
        <Link className="button secondary" to="/">
          Back to the feed
        </Link>
      </div>
    );
  }

  const isOwner = profile?.id === photo.owner_id;

  return (
    <section>
      <div className="spread">
        <div>
          <h1>{photo.caption || "Untitled photo"}</h1>
          <p className="lede">
            @{photo.owner_username} · {new Date(photo.created_at).toLocaleString()} ·{" "}
            {photo.visibility === "owner" ? "Only the owner" : "Friends"}
          </p>
        </div>
        <Link className="button secondary" to="/">
          Back to the feed
        </Link>
      </div>

      {src ? (
        <img className="photo-large" src={src} alt={photo.caption || "Photo"} />
      ) : (
        <p className="empty">The image could not be loaded. The signed link may have expired.</p>
      )}

      <p>
        {photo.tags.map((tag) => (
          <span className="tag" key={tag}>
            {tag}
          </span>
        ))}
      </p>

      {isOwner && (
        <ConfirmButton
          onConfirm={removePhoto}
          prompt="Delete this photo permanently? This cannot be undone."
        >
          Delete photo
        </ConfirmButton>
      )}

      <h2>Comments ({comments.length})</h2>

      {comments.length === 0 && <p className="lede">No comments yet.</p>}

      <div>
        {comments.map((comment) => (
          <div className="comment" key={comment.id}>
            <p style={{ margin: 0 }}>{comment.body}</p>
            <p className="meta">
              @{comment.author_username} · {new Date(comment.created_at).toLocaleString()}
              {(comment.author_id === profile?.id || isOwner) && (
                <>
                  {" · "}
                  <button
                    type="button"
                    className="link"
                    onClick={() => removeComment(comment.id)}
                  >
                    Delete
                  </button>
                </>
              )}
            </p>
          </div>
        ))}
      </div>

      <form onSubmit={submitComment} style={{ marginTop: "1rem" }}>
        <ErrorBanner message={commentError} />
        <Field id="comment" label="Add a comment">
          <textarea
            id="comment"
            value={body}
            maxLength={2000}
            onChange={(event) => setBody(event.target.value)}
          />
        </Field>
        <button className="button" type="submit" disabled={posting}>
          {posting ? "Posting" : "Post comment"}
        </button>
      </form>
    </section>
  );
}
