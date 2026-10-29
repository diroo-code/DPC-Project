// Small presentational pieces. Every one of them has an accessible name or role.

export function Spinner({ label = "Loading" }) {
  return (
    <div className="spinner" role="status" aria-live="polite">
      <span className="spinner-dot" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorBanner({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="banner banner-error" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="link" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Notice({ children }) {
  return (
    <div className="banner banner-notice" role="note">
      {children}
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

export function Field({ id, label, hint, error, children }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && !error && <p className="hint">{hint}</p>}
      {error && (
        <p className="field-error" id={`${id}-error`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function ConfirmButton({ onConfirm, children, className = "button danger", prompt }) {
  return (
    <button
      type="button"
      className={className}
      onClick={() => {
        if (window.confirm(prompt)) onConfirm();
      }}
    >
      {children}
    </button>
  );
}
