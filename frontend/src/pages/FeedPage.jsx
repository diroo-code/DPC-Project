import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ErrorBanner, EmptyState, Field, Spinner } from "../components/ui.jsx";
import { listPhotos, mediaUrl, photoUrl, searchPhotos } from "../lib/api.js";

function PhotoCard({ photo }) {
  const [src, setSrc] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    photoUrl(photo.id)
      .then((data) => {
        if (alive) setSrc(mediaUrl(data.url));
      })
      .catch((problem) => {
        if (alive) setError(problem.message);
      });
    return () => {
      alive = false;
    };
  }, [photo.id]);

  return (
    <article className="photo-card">
      {src ? (
        <img src={src} alt={photo.caption || `Photo by ${photo.owner_username}`} loading="lazy" />
      ) : (
        <div className="empty" style={{ border: 0, padding: "2.5rem 1rem" }}>
          {error ? "Image unavailable" : "Loading image"}
        </div>
      )}
      <div className="body">
        <Link to={`/photos/${photo.id}`}>
          <strong>{photo.caption || "Untitled photo"}</strong>
        </Link>
        <p className="meta">
          @{photo.owner_username} · {new Date(photo.created_at).toLocaleDateString()} ·{" "}
          {photo.comment_count} comment{photo.comment_count === 1 ? "" : "s"}
        </p>
        <p>
          {photo.tags.map((tag) => (
            <span className="tag" key={tag}>
              {tag}
            </span>
          ))}
        </p>
      </div>
    </article>
  );
}

export function FeedPage({ searchMode = false }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({ q: "", tag: "", uploader: "", dateFrom: "", dateTo: "" });
  const [applied, setApplied] = useState({ q: "", tag: "", uploader: "", dateFrom: "", dateTo: "" });

  const load = useCallback(
    async (offset = 0, active = applied) => {
      setLoading(true);
      setError("");
      try {
        const fetcher = searchMode ? searchPhotos : listPhotos;
        if (searchMode && !active.q) {
          setItems([]);
          setTotal(0);
          setHasMore(false);
          return;
        }
        const data = await fetcher({
          q: active.q,
          tag: active.tag || undefined,
          uploader: active.uploader || undefined,
          dateFrom: active.dateFrom || undefined,
          dateTo: active.dateTo || undefined,
          limit: 12,
          offset,
        });
        setItems((previous) => (offset === 0 ? data.items : [...previous, ...data.items]));
        setTotal(data.total);
        setHasMore(data.has_more);
      } catch (problem) {
        setError(problem.message);
      } finally {
        setLoading(false);
      }
    },
    [applied, searchMode],
  );

  useEffect(() => {
    load(0, applied);
  }, [applied, load]);

  function apply(event) {
    event.preventDefault();
    setApplied({ ...filters });
  }

  return (
    <section>
      <h1>{searchMode ? "Search photos" : "Your feed"}</h1>
      <p className="lede">
        {searchMode
          ? "Find photos you are allowed to see by caption, tag, uploader or date."
          : "Photos you own, and photos your friends have shared with you."}
      </p>

      <form className="filters" onSubmit={apply}>
        {searchMode && (
          <Field id="q" label="Caption contains">
            <input
              id="q"
              value={filters.q}
              onChange={(event) => setFilters({ ...filters, q: event.target.value })}
              placeholder="sunset"
            />
          </Field>
        )}
        <Field id="tag" label="Tag">
          <input
            id="tag"
            value={filters.tag}
            onChange={(event) => setFilters({ ...filters, tag: event.target.value })}
            placeholder="hiking"
          />
        </Field>
        <Field id="uploader" label="Uploader">
          <input
            id="uploader"
            value={filters.uploader}
            onChange={(event) => setFilters({ ...filters, uploader: event.target.value })}
            placeholder="username"
          />
        </Field>
        <Field id="from" label="From">
          <input
            id="from"
            type="date"
            value={filters.dateFrom}
            onChange={(event) => setFilters({ ...filters, dateFrom: event.target.value })}
          />
        </Field>
        <Field id="to" label="To">
          <input
            id="to"
            type="date"
            value={filters.dateTo}
            onChange={(event) => setFilters({ ...filters, dateTo: event.target.value })}
          />
        </Field>
        <button className="button" type="submit">
          {searchMode ? "Search" : "Apply filters"}
        </button>
      </form>

      <ErrorBanner message={error} onRetry={() => load(0, applied)} />

      {loading && items.length === 0 && <Spinner label="Loading photos" />}

      {!loading && items.length === 0 && !error && (
        <EmptyState title={searchMode ? "No matching photos" : "Nothing here yet"}>
          <p>
            {searchMode
              ? "Try a different word, tag or uploader."
              : "Upload a photo, or add a friend to see what they share."}
          </p>
          {!searchMode && (
            <Link className="button" to="/upload">
              Upload a photo
            </Link>
          )}
        </EmptyState>
      )}

      <div className="grid">
        {items.map((photo) => (
          <PhotoCard key={photo.id} photo={photo} />
        ))}
      </div>

      <div className="spread" style={{ marginTop: "1.25rem" }}>
        <span className="meta">
          {items.length} of {total} photo{total === 1 ? "" : "s"}
        </span>
        {hasMore && (
          <button
            type="button"
            className="button secondary"
            disabled={loading}
            onClick={() => load(items.length, applied)}
          >
            {loading ? "Loading" : "Load more"}
          </button>
        )}
      </div>
    </section>
  );
}
