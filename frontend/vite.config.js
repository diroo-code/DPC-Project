import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxyTarget = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";

// The policy is generated from the configured origins, so a build pointed at a real API and a real
// Supabase project allows exactly those origins and nothing wider. frame-ancestors is omitted here
// because browsers ignore it in a meta tag; the hosting header in public/_headers carries it.
function contentSecurityPolicy() {
  const connect = new Set(["'self'"]);
  const img = new Set(["'self'", "data:", "blob:"]);

  for (const value of [process.env.VITE_API_BASE_URL, process.env.VITE_SUPABASE_URL]) {
    if (!value) continue;
    try {
      const origin = new URL(value).origin;
      connect.add(origin);
      img.add(origin);
    } catch {
      // An invalid URL is ignored here; configuration errors are reported during deployment review.
    }
  }

  return [
    "default-src 'self'",
    "script-src 'self'",
    // React style attributes require inline styles. Scripts do not, and that is the directive that matters.
    "style-src 'self' 'unsafe-inline'",
    `img-src ${[...img].join(" ")}`,
    "font-src 'self'",
    `connect-src ${[...connect].join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "upgrade-insecure-requests",
  ].join("; ");
}

function cspMetaPlugin() {
  return {
    name: "inject-csp-meta",
    apply: "build",
    transformIndexHtml(html) {
      const tag = `<meta http-equiv="Content-Security-Policy" content="${contentSecurityPolicy()}" />`;
      return html.replace("</head>", `    ${tag}\n  </head>`);
    },
  };
}

export default defineConfig({
  plugins: [react(), cspMetaPlugin()],
  // The test transform needs the automatic JSX runtime explicitly, otherwise JSX compiles to
  // React.createElement and every file would need a React import it does not use.
  esbuild: { jsx: "automatic" },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // Keeps the browser on one origin during development, which avoids CORS surprises.
      "/api": { target: proxyTarget, changeOrigin: true },
      "/media": { target: proxyTarget, changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.js"],
    css: false,
  },
});
