#!/usr/bin/env bash
# Phase 2 live acceptance: a real server, a real database, three real users, and the full journey.
set -u
cd /workspace/projects/TEB3033-Photo-Sharing/backend
. .venv/bin/activate

DB=itp_phase2_live
PORT=8125
export PGPASSWORD=itp_local_only
export DATABASE_URL="postgresql://itp_app:itp_local_only@127.0.0.1:5432/${DB}"
export SUPABASE_JWT_SECRET="$(openssl rand -hex 32)"
export STORAGE_BACKEND=local
export STORAGE_LOCAL_ROOT=/tmp/itp_phase2_storage
export STORAGE_SIGNING_SECRET="$(openssl rand -hex 32)"
export APP_ENV=test

rm -rf /tmp/itp_phase2_storage
psql -h 127.0.0.1 -U itp_app -d postgres -q -c "drop database if exists ${DB} with (force)" 2>/dev/null
psql -h 127.0.0.1 -U itp_app -d postgres -q -c "create database ${DB} with encoding 'UTF8' template template0"
psql -h 127.0.0.1 -U itp_app -d "${DB}" -q -v ON_ERROR_STOP=1 -f ../database/testing/000_local_supabase_stub.sql >/dev/null
for m in ../database/migrations/*.sql; do
  psql -h 127.0.0.1 -U itp_app -d "${DB}" -q -v ON_ERROR_STOP=1 -f "$m" >/dev/null || exit 1
done
echo "database ready: tables $(psql -h 127.0.0.1 -U itp_app -d ${DB} -tAc "select count(*) from information_schema.tables where table_schema='public'")"

python - <<'PY'
import jwt, psycopg, uuid
from datetime import datetime, timedelta, timezone
from psycopg.types.json import Jsonb

url = "postgresql://itp_app:itp_local_only@127.0.0.1:5432/itp_phase2_live"
import os
secret = os.environ["SUPABASE_JWT_SECRET"]
users = {}
with psycopg.connect(url, autocommit=True) as c:
    for name in ("alice", "bob", "carol"):
        uid = uuid.uuid4()
        c.execute(
            "insert into auth.users (id, email, raw_user_meta_data) values (%s, %s, %s)",
            (uid, f"{name}@example.test", Jsonb({"username": name, "display_name": name.title()})),
        )
        users[name] = str(uid)
        payload = {
            "sub": str(uid), "aud": "authenticated", "role": "authenticated",
            "email": f"{name}@example.test",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()),
        }
        open(f"/tmp/p2_{name}.token", "w").write(jwt.encode(payload, secret, algorithm="HS256"))
print("users:", users)
PY

printf '\xff\xd8\xff\xe0' > /tmp/p2_photo.jpg
head -c 2048 /dev/urandom >> /tmp/p2_photo.jpg

python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning > /tmp/p2_uvicorn.log 2>&1 &
UV=$!
for i in $(seq 1 40); do curl -s -o /dev/null --max-time 1 "http://127.0.0.1:${PORT}/health" && break; sleep 0.25; done

A="Authorization: Bearer $(cat /tmp/p2_alice.token)"
B="Authorization: Bearer $(cat /tmp/p2_bob.token)"
C="Authorization: Bearer $(cat /tmp/p2_carol.token)"
BASE="http://127.0.0.1:${PORT}"

echo
echo "=== 1. alice uploads a photo ==="
CODE=$(curl -s -o /tmp/p2_upload.json -w '%{http_code}' -X POST -H "$A" \
  -F "file=@/tmp/p2_photo.jpg;type=image/jpeg" -F "caption=Lake at dusk" \
  -F "visibility=friends" -F "tags=sunset,lake" "$BASE/api/v1/photos")
PHOTO=$(python -c "import json;print(json.load(open('/tmp/p2_upload.json'))['id'])")
echo "   status $CODE  id $PHOTO  $(python -c "import json;d=json.load(open('/tmp/p2_upload.json'));print(d['owner_username'], d['tags'])")"

echo
echo "=== 2. carol uploads her own photo (control) ==="
CODE=$(curl -s -o /tmp/p2_upload_c.json -w '%{http_code}' -X POST -H "$C" \
  -F "file=@/tmp/p2_photo.jpg;type=image/jpeg" -F "caption=Carol private" \
  -F "visibility=owner" "$BASE/api/v1/photos")
echo "   status $CODE"

echo
echo "=== 3. bob is not yet a friend, so he must not see alice's photo ==="
curl -s -H "$B" "$BASE/api/v1/photos" > /tmp/p2_feed_before.json
python -c "import json;d=json.load(open('/tmp/p2_feed_before.json'));print('   bob feed total:', d['total'], '| items:', len(d['items']))"
echo "   bob photo url: $(curl -s -o /dev/null -w '%{http_code}' -H "$B" "$BASE/api/v1/photos/$PHOTO/url")"

echo
echo "=== 4. alice sends a friend request, bob accepts ==="
curl -s -H "$A" -H 'Content-Type: application/json' -d '{"username":"bob"}' "$BASE/api/v1/friends/requests" > /tmp/p2_req.json
REQ=$(python -c "import json;print(json.load(open('/tmp/p2_req.json'))['id'])")
echo "   request $REQ status $(python -c "import json;print(json.load(open('/tmp/p2_req.json'))['status'])")"
echo "   bob accepts: $(curl -s -o /dev/null -w '%{http_code}' -X POST -H "$B" "$BASE/api/v1/friends/requests/$REQ/accept")"

echo
echo "=== 5. bob can now see the feed and comment ==="
curl -s -H "$B" "$BASE/api/v1/photos" > /tmp/p2_feed_after.json
python -c "import json;d=json.load(open('/tmp/p2_feed_after.json'));print('   bob feed total:', d['total'], '| captions:', [i['caption'] for i in d['items']])"
echo "   bob comment: $(curl -s -o /tmp/p2_comment.json -w '%{http_code}' -X POST -H "$B" -H 'Content-Type: application/json' -d '{"body":"Lovely light"}' "$BASE/api/v1/photos/$PHOTO/comments")"
echo "   alice sees comments: $(curl -s -H "$A" "$BASE/api/v1/photos/$PHOTO/comments" | python -c "import json,sys;d=json.load(sys.stdin);print([(c['author_username'],c['body']) for c in d])")"

echo
echo "=== 6. signed URL: bob allowed, carol refused, tampering rejected ==="
curl -s -H "$B" "$BASE/api/v1/photos/$PHOTO/url" > /tmp/p2_url.json
URL=$(python -c "import json;print(json.load(open('/tmp/p2_url.json'))['url'])")
echo "   bob url issued: ${URL:0:60}...  ttl=$(python -c "import json;print(json.load(open('/tmp/p2_url.json'))['expires_in'])")s"
echo "   fetching it: $(curl -s -o /tmp/p2_download.jpg -w '%{http_code} %{size_download} bytes' "$BASE$URL")"
echo "   bytes identical: $(cmp -s /tmp/p2_photo.jpg /tmp/p2_download.jpg && echo yes || echo no)"
echo "   carol url request: $(curl -s -o /dev/null -w '%{http_code}' -H "$C" "$BASE/api/v1/photos/$PHOTO/url")"
echo "   tampered signature: $(curl -s -o /dev/null -w '%{http_code}' "$BASE${URL%????}0000")"

echo
echo "=== 7. alice deletes the photo; it disappears for bob ==="
echo "   delete status: $(curl -s -o /dev/null -w '%{http_code}' -X DELETE -H "$A" "$BASE/api/v1/photos/$PHOTO")"
echo "   bob feed after delete: $(curl -s -H "$B" "$BASE/api/v1/photos" | python -c "import json,sys;print(json.load(sys.stdin)['total'])")"
echo "   object on disk: $(find /tmp/itp_phase2_storage -type f | wc -l) file(s) remaining (carol's)"

echo
echo "=== 8. permissions that must fail ==="
echo "   bob deletes carol's owner-only photo (invisible to him, expect 404): $(curl -s -o /dev/null -w '%{http_code}' -X DELETE -H "$B" "$BASE/api/v1/photos/$(python -c "import json;print(json.load(open('/tmp/p2_upload_c.json'))['id'])")")"
echo "   carol accepts a request not addressed to her (should be 403): $(curl -s -o /dev/null -w '%{http_code}' -X POST -H "$C" "$BASE/api/v1/friends/requests/$REQ/accept")"
echo "   unauthenticated upload (should be 401): $(curl -s -o /dev/null -w '%{http_code}' -X POST -F 'file=@/tmp/p2_photo.jpg;type=image/jpeg' "$BASE/api/v1/photos")"

echo
kill "$UV" 2>/dev/null
wait "$UV" 2>/dev/null
sleep 0.5
echo "=== server stopped: $(kill -0 "$UV" 2>/dev/null && echo no || echo yes) | log lines: $(wc -l < /tmp/p2_uvicorn.log) ==="
cat /tmp/p2_uvicorn.log | sed 's/^/   /'
