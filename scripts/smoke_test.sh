#!/usr/bin/env bash
#
# Verifies a running Grade Change Intelligence deployment.
#
# Checks the things a "successful deploy" can still get wrong: that the models
# actually loaded, that every endpoint the UI depends on answers, that the
# held-out metrics are unchanged inside the deployed artifact, and that the
# client-side routes return the app shell rather than a 404.
#
#   ./scripts/smoke_test.sh                          # defaults to localhost:8000
#   ./scripts/smoke_test.sh https://your-host.app    # a live deployment
#
# Exits non-zero on the first failure, so it is usable as a CI gate or as a
# post-deploy check against a real URL.

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
BASE_URL="${BASE_URL%/}"

# Model training happens at startup, so a cold service needs a grace period
# before it answers at all. Override for a slower host.
READY_ATTEMPTS="${READY_ATTEMPTS:-40}"
READY_INTERVAL="${READY_INTERVAL:-3}"

# The evaluation figures this build is expected to report. If a dependency
# resolves differently in the deployed image, this is what catches it.
EXPECTED_METRICS=('"test_accuracy":0.945' '"test_f1":0.881' '"test_r2":0.985')

pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1" >&2; exit 1; }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }

step "Target: ${BASE_URL}"

# ── Readiness ────────────────────────────────────────────────────────────────
step 'Waiting for readiness'
health=''
for attempt in $(seq 1 "${READY_ATTEMPTS}"); do
  if health=$(curl -fsS --max-time 10 "${BASE_URL}/api/health" 2>/dev/null); then
    pass "ready after ${attempt} attempt(s)"
    break
  fi
  sleep "${READY_INTERVAL}"
done
[ -n "${health}" ] || fail "no response from ${BASE_URL}/api/health"

echo "  ${health}"
case "${health}" in
  *'"status":"ready"'*) pass 'status is ready' ;;
  *) fail 'service is not reporting ready' ;;
esac
case "${health}" in
  *'"events":119'*) pass 'all 119 events loaded' ;;
  *) fail 'event count is wrong — the datasets may be missing from the image' ;;
esac

# ── API surface ──────────────────────────────────────────────────────────────
# Includes a scored prediction and its recommendations, so the classifier,
# regressor and KNN recovery engine are all proven to run in the deployment.
step 'API endpoints'
for path in \
  '/api/events' \
  '/api/events/46/timeline' \
  '/api/events/46/predict?t=180' \
  '/api/events/46/projection?t=180' \
  '/api/events/46/recommendations?t=180' \
  '/api/correlations' \
  '/api/recipe-limits/Grade-B-Std?event_id=46&t=180' \
  '/api/optimal-setpoints/Grade-B-Std' \
  '/api/feedback' \
  '/api/model-info'
do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "${BASE_URL}${path}")
  [ "${code}" = '200' ] || fail "${code} ${path}"
  pass "200  ${path}"
done

# ── Model integrity ──────────────────────────────────────────────────────────
step 'Held-out metrics'
info=$(curl -fsS --max-time 30 "${BASE_URL}/api/model-info")
for expected in "${EXPECTED_METRICS[@]}"; do
  case "${info}" in
    *"${expected}"*) pass "${expected}" ;;
    *) printf '%s\n' "${info}" >&2; fail "metric drifted, expected ${expected}" ;;
  esac
done

# ── Served frontend ──────────────────────────────────────────────────────────
step 'Frontend and client routes'
for path in '/' '/correlations' '/events' '/feedback'; do
  out=$(curl -s -o /dev/null -w '%{http_code} %{content_type}' --max-time 30 "${BASE_URL}${path}")
  code=${out%% *}
  type=${out#* }
  [ "${code}" = '200' ] || fail "${code} ${path}"
  case "${type}" in
    text/html*) pass "200 html  ${path}" ;;
    *) fail "${path} returned ${type}, expected HTML" ;;
  esac
done

# An unknown API path must stay JSON. If it fell through to the SPA shell, a
# client would fail parsing HTML instead of seeing the real status.
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "${BASE_URL}/api/nope")
[ "${code}" = '404' ] || fail "unknown API path returned ${code}, expected 404"
pass '404  /api/nope stays JSON'

# The hashed bundle referenced by index.html must actually be served.
asset=$(curl -fsS --max-time 30 "${BASE_URL}/" | grep -o '/assets/index-[A-Za-z0-9_-]*\.js' | head -1)
[ -n "${asset}" ] || fail 'index.html references no JS bundle'
curl -fsS -o /dev/null --max-time 30 "${BASE_URL}${asset}" || fail "bundle ${asset} not served"
pass "bundle served  ${asset}"

printf '\n\033[32mAll checks passed.\033[0m %s is serving the app.\n' "${BASE_URL}"
