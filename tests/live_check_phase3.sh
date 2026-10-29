#!/usr/bin/env bash
# Phase 3 live check: the brief's literal paths on a real Uvicorn process.
set -u
cd /workspace/projects/TEB3033-Photo-Sharing/backend
. .venv/bin/activate

DB=itp_phase3_live
PORT=8126
export PGPASSWORD=itp_local_only
export DATABASE_URL="postgresql://itp_app:itp_local_only@127.0.0.1:5432/${DB}"
export SUPABASE_JWT_SECRET="$(openssl rand -hex 32)"
export STORAGE_BACKEND=local
export STORAGE_LOCAL_ROOT=/tmp/itp_phase3_storage
export STORAGE_SIGNING_SECRET="$(openssl rand -hex 32)"
export APP_ENV=test
rm -rf /tmp/itp_phase3_storage

psql -h 127.0.0.1 -U itp_app -d postgres -q -c "drop database if exists ${DB} with (force)" 2>/dev/null
psql -h 127.0.0.1 -U itp_app -d postgres -q -c "create database ${DB} with encoding 'UTF8' template template0"
psql -h 127.0.0.1 -U itp_app -d "${DB}" -q -v ON_ERROR_STOP=1 -f ../database/testing/000_local_supabase_stub.sql >/dev/null
for m in ../database/migrations/*.sql; do
  psql -h 127.0.0.1 -U itp_app -d "${DB}" -q -v ON_ERROR_STOP=1 -f "$m" >/dev/null || exit 1
done

python - <<'PY'
import jwt, psycopg, uuid
from datetime import datetime, timedelta, timezone
from psycopg.types.json import Jsonb
url = "postgresql://itp_app:itp_local_only@127.0.0.1:5432/itp_phase3_live"
import os
secret = os.environ["SUPABASE_JWT_SECRET"]
with psycopg.connect(url, autocommit=True) as c:
    for name in ("alice", "bob"):
        uid = uuid.uuid4()
        c.execute("insert into auth.users (id, email, raw_user_meta_data) values (%s,%s,%s)",
                  (uid, f"{name}@example.test", Jsonb({"username": name, "display_name": name.title()})))
        open(f"/tmp/p3_{name}.token", "w").write(jwt.encode({
            "sub": str(uid), "aud": "authenticated", "role": "authenticated",
            "email": f"{name}@example.test",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()),
        }, secret, algorithm="HS256"))
        open(f"/tmp/p3_{name}.id", "w").write(str(uid))
PY

printf '\xff\xd8\xff\xe0' > /tmp/p3.jpg; head -c 1024 /dev/urandom >> /tmp/p3.jpg

python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning > /tmp/p3_uvicorn.log 2>&1 &
UV=$!
for i in $(seq 1 40); do curl -s -o /dev/null --max-time 1 "http://127.0.0.1:${PORT}/health" && break; sleep 0.25; done

A="Authorization: Bearer $(cat /tmp/p3_alice.token)"
B="Authorization: Bearer $(cat /tmp/p3_bob.token)"
BASE="http://127.0.0.1:${PORT}"
ALICE_ID=$(cat /tmp/p3_alice.id)

echo "=== brief paths on a live server ==="
echo "   GET /health              -> $(curl -s -o /dev/null -w '%{http_code}' $BASE/health)"
echo "   GET /me (no token)       -> $(curl -s -o /dev/null -w '%{http_code}' $BASE/me)"
echo "   GET /me                  -> $(curl -s -o /tmp/p3_me.json -w '%{http_code}' -H "$A" $BASE/me) $(cat /tmp/p3_me.json)"
echo "   GET /profiles/{id}       -> $(curl -s -o /tmp/p3_prof.json -w '%{http_code}' -H "$B" $BASE/profiles/$ALICE_ID) $(cat /tmp/p3_prof.json)"
echo "   GET /profiles/unknown    -> $(curl -s -o /dev/null -w '%{http_code}' -H "$B" $BASE/profiles/00000000-0000-0000-0000-000000000000)"

curl -s -X POST -H "$A" -F "file=@/tmp/p3.jpg;type=image/jpeg" -F "caption=Sunset over the lake" -F "tags=sunset" $BASE/photos > /tmp/p3_upload.json
PHOTO=$(python -c "import json;print(json.load(open('/tmp/p3_upload.json'))['id'])")
echo "   POST /photos             -> id $(echo $PHOTO | cut -c1-8)..."

echo "   GET /photos              -> $(curl -s -o /tmp/p3_feed.json -w '%{http_code}' -H "$A" $BASE/photos) total=$(python -c "import json;print(json.load(open('/tmp/p3_feed.json'))['total'])")"
echo "   GET /photos/search?q=sun -> $(curl -s -o /tmp/p3_search.json -w '%{http_code}' -H "$A" "$BASE/photos/search?q=sunset") total=$(python -c "import json;print(json.load(open('/tmp/p3_search.json'))['total'])")"
echo "   GET /photos/search (no q)-> $(curl -s -o /dev/null -w '%{http_code}' -H "$A" $BASE/photos/search)"
echo "   GET /photos/{id}/comments-> $(curl -s -o /dev/null -w '%{http_code}' -H "$A" $BASE/photos/$PHOTO/comments)"
echo "   GET /friends             -> $(curl -s -o /dev/null -w '%{http_code}' -H "$A" $BASE/friends)"
echo "   GET /photos/{id}         -> $(curl -s -o /dev/null -w '%{http_code}' -H "$A" $BASE/photos/$PHOTO)"
echo "   DELETE /photos/{id}      -> $(curl -s -o /dev/null -w '%{http_code}' -X DELETE -H "$A" $BASE/photos/$PHOTO)"

kill "$UV" 2>/dev/null
wait "$UV" 2>/dev/null
echo "=== server stopped, log lines: $(wc -l < /tmp/p3_uvicorn.log) ==="
cat /tmp/p3_uvicorn.log | sed 's/^/   /'
