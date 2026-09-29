# Shared helpers for fast.sh and full.sh: run a step with its log and time, then summarise.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS="$ROOT/src/tests/_out/logs"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
[ -x "$PY" ] || PY=python3
mkdir -p "$LOGS"
rm -f "$LOGS"/*.log "$LOGS"/*.status
cd "$ROOT" || exit 1
ORDER=()

# run NAME ARGS...: run a Python script, log to $LOGS/NAME.log, record "exit-code seconds".
run() {
  local name=$1 start
  shift
  start=$(date +%s)
  "$PY" "$@" >"$LOGS/$name.log" 2>&1
  echo "$? $(($(date +%s) - start))" >"$LOGS/$name.status"
}

# summary: print one line per step in ORDER; exit non-zero if any failed or did not finish.
summary() {
  local name rc secs failed=0
  echo
  for name in "${ORDER[@]}"; do
    if [ -f "$LOGS/$name.status" ]; then
      read -r rc secs <"$LOGS/$name.status"
    else
      rc=skipped secs=-
    fi
    if [ "$rc" = 0 ]; then
      printf 'PASS  %-10s %5ss\n' "$name" "$secs"
    else
      failed=1
      printf 'FAIL  %-10s %5ss  exit %s, log %s\n' "$name" "$secs" "$rc" "src/tests/_out/logs/$name.log"
      [ -f "$LOGS/$name.log" ] && grep -E 'FAIL|Error|Traceback|Replay' "$LOGS/$name.log" | head -5 | sed 's/^/      /'
    fi
  done
  printf 'TOTAL %s  %ss\n' "$([ $failed = 0 ] && echo PASS || echo FAIL)" "$(($(date +%s) - T0))"
  return $failed
}

T0=$(date +%s)
