#!/usr/bin/env bash
# Phase 1 live acceptance test. Starts a real Uvicorn process against a real PostgreSQL database
# built from the production migration, then exercises the endpoints with a real signed token.
set -u
cd /workspace/projects/TEB3033-Photo-Sharing/backend
. .venv/bin/activate

DB=itp_photo_live
PORT=8124
export PGPASSWORD=itp_local_only
export DATABASE_URL="postgresql://itp_app:itp_local_only@127.0.0.1:5432/${DB}"
export SUPABASE_JWT_SECRET="$(openssl rand -hex 32)"
export APP_ENV=test

echo "=== building a fresh database from the migrations ==="
psql -h 127.0.0.1 -U itp_app -d postgres -q -c "drop database if exists ${DB} with (force)" 2>&1
psql -h 127.0.0.1 -U itp_app -d postgres -q -c "create database ${DB} with encoding 'UTF8' template template0" 2>&1
psql -h 127.0.0.1 -U itp_app -d "${DB}" -v ON_ERROR_STOP=1 -q -f ../database/testing/000_local_supabase_stub.sql 2>&1 | grep -v NOTICE
psql -h 127.0.0.1 -U itp_app -d "${DB}" -v ON_ERROR_STOP=1 -q -f ../database/migrations/001_init.sql 2>&1 | grep -v NOTICE
echo "   database ready"

echo
echo "=== creating a test account through the auth trigger ==="
python - <<'PY'
import json, os, uuid, psycopg, jwt
from datetime import datetime, timedelta, timezone
from psycopg.types.json import Jsonb

url = "postgresql://itp_app:itp_local_only@127.0.0.1:5432/itp_photo_live"
uid = uuid.uuid4()
with psycopg.connect(url, autocommit=True) as c:
    c.execute(
        "insert into auth.users (id, email, raw_user_meta_data) values (%s, %s, %s)",
        (uid, "phase1@example.test", Jsonb({"username": "phase1", "display_name": "Phase One"})),
    )
payload = {
    "sub": str(uid), "aud": "authenticated", "role": "authenticated",
    "email": "phase1@example.test", "iat": int(datetime.now(timezone.utc).timestamp()),
    "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
}
token = jwt.encode(payload, os.environ["SUPABASE_JWT_SECRET"], algorithm="HS256")
open("/tmp/phase1_token.txt", "w").write(token)
open("/tmp/phase1_uid.txt", "w").write(str(uid))
print(f"   user {uid} created, profile row expected via trigger")
PY

echo
echo "=== starting uvicorn ==="
python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning > /tmp/phase1_uvicorn.log 2>&1 &
UV=$!
READY=0
for i in $(seq 1 40); do
  if curl -s -o /dev/null --max-time 1 "http://127.0.0.1:${PORT}/health"; then READY=1; break; fi
  sleep 0.25
done
echo "   pid $UV, ready=$READY"
TOKEN=$(cat /tmp/phase1_token.txt)

echo
echo "=== acceptance checks ==="
printf '   GET /health            -> %s  %s\n' \
  "$(curl -s -o /tmp/p1_health.json -w '%{http_code}' http://127.0.0.1:$PORT/health)" "$(cat /tmp/p1_health.json)"
printf '   GET /ready             -> %s  %s\n' \
  "$(curl -s -o /tmp/p1_ready.json -w '%{http_code}' http://127.0.0.1:$PORT/ready)" "$(cat /tmp/p1_ready.json)"
printf '   GET /auth/me no token  -> %s  %s\n' \
  "$(curl -s -o /tmp/p1_noauth.json -w '%{http_code}' http://127.0.0.1:$PORT/api/v1/auth/me)" "$(cat /tmp/p1_noauth.json)"
printf '   GET /auth/me bad token -> %s  %s\n' \
  "$(curl -s -o /tmp/p1_bad.json -w '%{http_code}' -H 'Authorization: Bearer not-a-jwt' http://127.0.0.1:$PORT/api/v1/auth/me)" "$(cat /tmp/p1_bad.json)"
printf '   GET /auth/me valid     -> %s  %s\n' \
  "$(curl -s -o /tmp/p1_me.json -w '%{http_code}' -H "Authorization: Bearer $TOKEN" http://127.0.0.1:$PORT/api/v1/auth/me)" "$(cat /tmp/p1_me.json)"
printf '   PATCH /auth/me         -> %s  %s\n' \
  "$(curl -s -o /tmp/p1_patch.json -w '%{http_code}' -X PATCH -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"display_name":"Phase One Updated","bio":"Verified in Phase 1."}' http://127.0.0.1:$PORT/api/v1/auth/me)" "$(cat /tmp/p1_patch.json)"
printf '   GET /docs              -> %s\n' "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/docs)"

echo
echo "=== stopping by pid ==="
kill "$UV" 2>/dev/null
wait "$UV" 2>/dev/null
sleep 0.5
if kill -0 "$UV" 2>/dev/null; then echo "   still running"; else echo "   stopped"; fi
printf '   port released: '; if ss -ltn 2>/dev/null | grep -q ":${PORT} "; then echo no; else echo yes; fi

echo
echo "=== server log (should be empty at warning level) ==="
cat /tmp/phase1_uvicorn.log | sed 's/^/   /'
echo "=== done ==="
