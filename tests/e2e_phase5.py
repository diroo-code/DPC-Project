"""Phase 5 end-to-end test: real browser, real servers, three controlled accounts.

Run with the Playwright interpreter: /root/.venvs/pdf/bin/python tests/e2e_phase5.py
It creates its own database, starts Uvicorn and the Vite dev server, drives Chromium, and cleans up.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import jwt
import psycopg
from playwright.sync_api import expect, sync_playwright
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DB = "itp_phase5_e2e"
JWT_SECRET = uuid.uuid4().hex + uuid.uuid4().hex
STORAGE = "/tmp/itp_phase5_storage"
PG = "postgresql://itp_app:itp_local_only@127.0.0.1:5432"
API = "http://127.0.0.1:8010"
WEB = "http://127.0.0.1:5175"

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))
    print(f"   {'PASS' if condition else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def wait_for(url: str, seconds: int = 40) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def build_database() -> dict[str, dict]:
    env = {**os.environ, "PGPASSWORD": "itp_local_only"}
    subprocess.run(["psql", "-h", "127.0.0.1", "-U", "itp_app", "-d", "postgres", "-q",
                    "-c", f'drop database if exists "{DB}" with (force)'], env=env, check=True)
    subprocess.run(["psql", "-h", "127.0.0.1", "-U", "itp_app", "-d", "postgres", "-q",
                    "-c", f'create database "{DB}" with encoding \'UTF8\' template template0'],
                   env=env, check=True)
    for sql in [ROOT / "database/testing/000_local_supabase_stub.sql",
                *sorted((ROOT / "database/migrations").glob("*.sql"))]:
        subprocess.run(["psql", "-h", "127.0.0.1", "-U", "itp_app", "-d", DB, "-q",
                        "-v", "ON_ERROR_STOP=1", "-f", str(sql)], env=env, check=True)

    users: dict[str, dict] = {}
    with psycopg.connect(f"{PG}/{DB}", autocommit=True) as conn:
        for name in ("alice", "bob", "carol"):
            uid = uuid.uuid4()
            conn.execute(
                "insert into auth.users (id, email, raw_user_meta_data) values (%s, %s, %s)",
                (uid, f"{name}@example.test",
                 Jsonb({"username": name, "display_name": name.title()})),
            )
            token = jwt.encode(
                {
                    "sub": str(uid), "aud": "authenticated", "role": "authenticated",
                    "email": f"{name}@example.test",
                    "iat": int(time.time()),
                    "exp": int(time.time()) + 7200,
                },
                JWT_SECRET,
                algorithm="HS256",
            )
            users[name] = {"id": str(uid), "token": token}
    return users


def main() -> int:
    print("=== preparing database ===")
    users = build_database()
    shutil.rmtree(STORAGE, ignore_errors=True)
    photo_file = Path("/tmp/e2e_photo.jpg")
    photo_file.write_bytes(b"\xff\xd8\xff\xe0" + os.urandom(4096))

    backend_env = {
        **os.environ,
        "DATABASE_URL": f"{PG}/{DB}",
        "SUPABASE_JWT_SECRET": JWT_SECRET,
        "STORAGE_BACKEND": "local",
        "STORAGE_LOCAL_ROOT": STORAGE,
        "STORAGE_SIGNING_SECRET": uuid.uuid4().hex + uuid.uuid4().hex,
        "CORS_ORIGINS": "http://127.0.0.1:5175,http://localhost:5175",
        "APP_ENV": "test",
    }
    frontend_env = {
        **os.environ,
        "VITE_DEV_AUTH": "1",
        "VITE_API_PROXY_TARGET": API,
    }

    print("=== starting servers ===")
    backend = subprocess.Popen(
        [str(BACKEND / ".venv/bin/python"), "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", "8010", "--log-level", "warning"],
        cwd=BACKEND, env=backend_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    frontend = subprocess.Popen(
        ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5175", "--strictPort"],
        cwd=FRONTEND, env=frontend_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )

    failures = 0
    try:
        if not wait_for(f"{API}/health"):
            print("backend did not start; last output:")
            try:
                backend.terminate()
                print((backend.stdout.read() or b"").decode("utf-8", "replace")[-800:])
            except Exception:
                pass
            return 1
        if not wait_for(f"{WEB}/"):
            print("frontend did not start"); return 1
        with urllib.request.urlopen(f"{WEB}/", timeout=2) as response:
            served = response.read().decode("utf-8", "replace")
        if "Photo Sharing" not in served:
            print("port 5175 is serving another application, refusing to test against it")
            return 1
        print("   both servers ready")

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)

            def context_for(name: str):
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                context.add_init_script(
                    f"sessionStorage.setItem('dev_access_token', {json.dumps(users[name]['token'])})"
                )
                return context, context.new_page()

            alice_ctx, alice = context_for("alice")
            console_log: list[str] = []
            alice.on("console", lambda message: console_log.append(f"{message.type}: {message.text}"))
            alice.goto(WEB, wait_until="networkidle")
            alice.wait_for_timeout(1500)
            feed_visible = alice.get_by_role("heading", name="Your feed").is_visible()
            if not feed_visible:
                print("   DEBUG url:", alice.url)
                print("   DEBUG body:", alice.inner_text("body")[:500].replace("\n", " | "))
                print("   DEBUG console:", console_log[-6:])
            check("alice lands on the feed", feed_visible)

            # ---- upload through the UI
            alice.get_by_role("link", name="Upload", exact=True).click()
            alice.get_by_label("Image").set_input_files(str(photo_file))
            alice.get_by_label("Caption").fill("Sunset over the lake")
            alice.get_by_label("Tags").fill("sunset, lake")
            alice.get_by_role("button", name="Upload").click()
            alice.wait_for_url("**/photos/**", timeout=15000)
            try:
                alice.get_by_role("heading", name="Sunset over the lake").wait_for(timeout=10000)
                uploaded = True
            except Exception:
                uploaded = False
            check("upload navigates to the photo", uploaded)
            check(
                "access token is not in localStorage",
                "dev_access_token" not in alice.evaluate("JSON.stringify(localStorage)"),
            )
            photo_url = alice.url
            photo_id = photo_url.rstrip("/").split("/")[-1]

            # ---- comment
            alice.get_by_label("Add a comment").fill("First comment")
            alice.get_by_role("button", name="Post comment").click()
            alice.wait_for_timeout(700)
            check("comment appears with the author", "First comment" in alice.content())

            # ---- source-level XSS attempt
            alice.goto(f"{WEB}/upload", wait_until="networkidle")
            alice.get_by_label("Image").set_input_files(str(photo_file))
            alice.get_by_label("Caption").fill('<img src=x onerror="window.__xss=1">')
            alice.get_by_role("button", name="Upload").click()
            alice.wait_for_url("**/photos/**", timeout=15000)
            alice.wait_for_timeout(800)
            check("script in a caption does not execute", alice.evaluate("window.__xss") is None)
            check("script in a caption is shown as text", "onerror" in alice.inner_text("body"))

            # ---- stranger: carol sees nothing
            carol_ctx, carol = context_for("carol")
            carol.goto(WEB, wait_until="networkidle")
            carol.wait_for_timeout(1500)
            carol_body = carol.content()
            if "Nothing here yet" not in carol_body:
                print("   DEBUG carol body:", carol.inner_text("body")[:300].replace("\n", " | "))
            check("stranger sees an empty feed", "Nothing here yet" in carol_body)
            check("stranger sees no photos at all", "Sunset over the lake" not in carol_body)
            carol.goto(f"{WEB}/photos/{photo_id}", wait_until="networkidle")
            check("stranger cannot open a friend-only photo", "not available to you" in carol.content())

            # ---- friendship workflow through the UI
            alice.goto(f"{WEB}/friends", wait_until="networkidle")
            alice.get_by_label("Add a friend by username").fill("bob")
            alice.get_by_role("button", name="Send request").click()
            alice.wait_for_timeout(700)
            check("alice sees the outgoing request", "Waiting for a reply" in alice.content())

            bob_ctx, bob = context_for("bob")
            bob.goto(f"{WEB}/friends", wait_until="networkidle")
            bob.get_by_role("button", name="Accept").first.click()
            bob.wait_for_timeout(800)
            check("bob accepts and sees alice as a friend", "@alice" in bob.content())

            bob.goto(WEB, wait_until="networkidle")
            check("friend now sees the shared photo", "Sunset over the lake" in bob.content())

            # ---- owner-only photo stays hidden
            alice.goto(f"{WEB}/upload", wait_until="networkidle")
            alice.get_by_label("Image").set_input_files(str(photo_file))
            alice.get_by_label("Caption").fill("Private note")
            alice.get_by_label("Only me").check()
            alice.get_by_role("button", name="Upload").click()
            alice.wait_for_url("**/photos/**", timeout=15000)
            private_id = alice.url.rstrip("/").split("/")[-1]
            bob.goto(f"{WEB}/photos/{private_id}", wait_until="networkidle")
            check("friend cannot open an owner-only photo", "not available to you" in bob.content())

            # ---- search
            alice.goto(f"{WEB}/search", wait_until="networkidle")
            alice.get_by_label("Caption contains").fill("sunset")
            alice.get_by_role("button", name="Search").click()
            alice.wait_for_timeout(900)
            check("search finds the matching photo", "Sunset over the lake" in alice.content())
            check("search excludes the private photo", "Private note" not in alice.content())

            # ---- profile edit
            alice.goto(f"{WEB}/profile", wait_until="networkidle")
            alice.get_by_label("Display name").fill("Alice Updated")
            alice.get_by_role("button", name="Save changes").click()
            alice.wait_for_timeout(800)
            check("profile save is confirmed", "Profile saved." in alice.content())

            browser.close()
    finally:
        for process in (frontend, backend):
            process.send_signal(signal.SIGTERM)
        for process in (frontend, backend):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        env = {**os.environ, "PGPASSWORD": "itp_local_only"}
        subprocess.run(["psql", "-h", "127.0.0.1", "-U", "itp_app", "-d", "postgres", "-q",
                        "-c", f'drop database if exists "{DB}" with (force)'], env=env)

    passed = sum(1 for _, ok, _ in results if ok)
    print()
    print(f"=== {passed} of {len(results)} checks passed ===")
    for name, ok, detail in results:
        if not ok:
            print(f"   FAILED: {name} {detail}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
