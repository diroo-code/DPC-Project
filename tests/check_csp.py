"""CSP and security header verification for the production build.

Static checks read the built files. A live check loads the build in Chromium and fails if the browser
refuses any resource, which is the only way to know the policy actually works.

Run after `npm run build`: backend/.venv/bin/python tests/check_csp.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"   {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    index = (DIST / "index.html").read_text(encoding="utf-8")
    headers = (DIST / "_headers").read_text(encoding="utf-8")

    match = re.search(
        r'<meta http-equiv="Content-Security-Policy" content="([^"]+)"', index
    )
    check("meta CSP present in the built page", match is not None)
    if not match:
        return 1
    csp = match.group(1)

    check("default-src is self only", "default-src 'self'" in csp)
    check("script-src has no unsafe-inline", "script-src 'self'" in csp and "unsafe-inline" not in csp.split("script-src")[1].split(";")[0])
    check("script-src has no unsafe-eval", "unsafe-eval" not in csp)
    check("object-src is none", "object-src 'none'" in csp)
    check("base-uri is self", "base-uri 'self'" in csp)
    check("frame-ancestors is set in the header policy", "frame-ancestors 'none'" in headers)
    check("header policy sets nosniff", "X-Content-Type-Options: nosniff" in headers)
    check("header policy sets referrer policy", "Referrer-Policy:" in headers)
    check("frame-ancestors is not in the meta tag, where browsers ignore it", "frame-ancestors" not in csp)

    # A build pointed at real origins must carry them, and only them.
    api = re.search(r"connect-src ([^;]+)", csp).group(1).split()
    check("connect-src is not open to the internet", "*" not in api and "https:" not in api, " ".join(api))

    print("   note: style-src allows 'unsafe-inline' for React inline style attributes; script-src does not")

    # ---- live browser check
    log = open("/tmp/csp_preview.log", "w")
    server = subprocess.Popen(
        ["npx", "vite", "preview", "--host", "127.0.0.1", "--port", "4174", "--strictPort"],
        cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen("http://127.0.0.1:4174/", timeout=1):
                    break
            except Exception:
                time.sleep(0.3)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            violations: list[str] = []
            page.on(
                "console",
                lambda message: violations.append(message.text)
                if "Content Security Policy" in message.text or "Refused to" in message.text
                else None,
            )
            page.goto("http://127.0.0.1:4174/", wait_until="networkidle")
            page.wait_for_timeout(1200)
            body = page.inner_text("body")
            check("the application renders under the policy", "Photo Sharing" in body)
            check("no CSP violations in the console", not violations, "; ".join(violations[:3]))
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        for pid in subprocess.run(
            ["ss", "-ltnp"], capture_output=True, text=True
        ).stdout.splitlines():
            if ":4174 " in pid:
                number = re.search(r"pid=(\d+)", pid)
                if number:
                    subprocess.run(["kill", number.group(1)])
        log.close()

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n=== {passed} of {len(results)} CSP checks passed ===")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
