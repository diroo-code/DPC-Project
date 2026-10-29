#!/usr/bin/env bash
# Phase 4 verification: serve the production build and check what actually ships.
set -u
cd /workspace/projects/TEB3033-Photo-Sharing/frontend

echo "=== bundle contents check ==="
echo "   files: $(find dist -type f | wc -l), total $(du -sh dist | cut -f1)"
if grep -rIl "service_role\|SERVICE_ROLE\|SUPABASE_SERVICE" dist/ >/dev/null 2>&1; then
  echo "   PRIVILEGED KEY REFERENCE FOUND IN BUNDLE"
else
  echo "   privileged key reference in bundle: none"
fi
if grep -rIl "eyJhbGciOi" dist/ >/dev/null 2>&1; then
  echo "   JWT-LIKE STRING FOUND IN BUNDLE"
else
  echo "   JWT-like strings in bundle: none"
fi

echo
echo "=== serving the production build ==="
npx vite preview --host 127.0.0.1 --port 4173 --strictPort > /tmp/phase4_preview.log 2>&1 &
PID=$!
READY=0
for i in $(seq 1 40); do
  if curl -s -o /dev/null --max-time 1 http://127.0.0.1:4173/; then READY=1; break; fi
  sleep 0.25
done

if [ "$READY" -eq 1 ]; then
  CODE=$(curl -s -o /tmp/phase4_index.html -w '%{http_code}' http://127.0.0.1:4173/)
  echo "   GET /            -> $CODE"
  ASSET=$(grep -o '/assets/index-[^"]*\.js' /tmp/phase4_index.html | head -1)
  CSS=$(grep -o '/assets/index-[^"]*\.css' /tmp/phase4_index.html | head -1)
  echo "   GET $ASSET -> $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:4173$ASSET")"
  echo "   GET $CSS -> $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:4173$CSS")"
  echo "   title: $(grep -o '<title>[^<]*</title>' /tmp/phase4_index.html)"
else
  echo "   preview server did not start"
  tail -5 /tmp/phase4_preview.log | sed 's/^/   /'
fi

kill "$PID" 2>/dev/null
wait "$PID" 2>/dev/null
# npx is a wrapper; the actual listener is a child, so it is stopped by its own pid.
for LISTENER in $(ss -ltnp 2>/dev/null | grep ':4173 ' | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u); do
  kill "$LISTENER" 2>/dev/null
done
sleep 0.5
if kill -0 "$PID" 2>/dev/null; then echo "   stop: wrapper still running"; else echo "   stop: clean"; fi
if ss -ltn 2>/dev/null | grep -q ':4173 '; then echo "   port still bound"; else echo "   port released"; fi
