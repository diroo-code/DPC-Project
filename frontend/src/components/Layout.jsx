import { Link, NavLink, Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../lib/auth.jsx";
import { Spinner } from "./ui.jsx";

export function Protected({ children }) {
  const auth = useAuth();
  const location = useLocation();

  if (auth.status === "loading") return <Spinner label="Checking your session" />;
  if (auth.status !== "signed_in") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}

export function Layout() {
  const { profile, signOut, status } = useAuth();

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="header">
        <Link to="/" className="brand">
          Photo Sharing
        </Link>

        {status === "signed_in" && (
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>
              Feed
            </NavLink>
            <NavLink to="/search">Search</NavLink>
            <NavLink to="/upload">Upload</NavLink>
            <NavLink to="/friends">Friends</NavLink>
            <NavLink to="/profile">Profile</NavLink>
          </nav>
        )}

        <div className="header-right">
          {status === "signed_in" ? (
            <>
              <span className="who">{profile ? `@${profile.username}` : ""}</span>
              <button type="button" className="link" onClick={signOut}>
                Sign out
              </button>
            </>
          ) : (
            <Link to="/login" className="link">
              Sign in
            </Link>
          )}
        </div>
      </header>

      <main id="main" className="main">
        <Outlet />
      </main>

      <footer className="footer">
        <span>TEB3033 Distributed Photo-Sharing and Commenting System</span>
      </footer>
    </div>
  );
}
