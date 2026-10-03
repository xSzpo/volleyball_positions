#!/usr/bin/env bash
# Once per ticket, after review fixes: build and audit, then every browser test in parallel.
source "$(dirname "$0")/lib.sh"

ORDER=(build audit qa-m qa-d theme analytics flags rules learn anim match-1 match-2 match-3 match-4 mp
  online online-wk report report-wk)
# Emulator ports from this checkout's path, so several worktrees can run full.sh at once.
SLOT=$(($(printf '%s' "$ROOT" | cksum | cut -d' ' -f1) % 2000))
export KSV_EMU_DB_PORT="${KSV_EMU_DB_PORT:-$((20000 + SLOT * 4))}"
export KSV_EMU_AUTH_PORT="${KSV_EMU_AUTH_PORT:-$((KSV_EMU_DB_PORT + 1))}"
run build src/build.py
run audit src/tests/audit.py
read -r rc _ <"$LOGS/build.status"
if [ "$rc" = 0 ]; then
  run qa-m src/tests/qa.py m &
  run qa-d src/tests/qa.py d --quick &
  for shard in 1 2 3 4; do
    run "match-$shard" src/tests/match_test.py --shard "$shard/4" &
  done
  run mp src/tests/mp_test.py &
  # All use this checkout's emulator ports, so they run one after the other.
  {
    run online src/tests/online_test.py
    run online-wk src/tests/online_test.py --webkit
    run report src/tests/report_test.py
    run report-wk src/tests/report_test.py --webkit
  } &
  {
    run theme src/tests/theme_test.py
    run analytics src/tests/analytics_test.py
    run flags src/tests/flags_test.py
    run rules src/tests/rules_test.py
    run learn src/tests/learn_test.py
  } &
  run anim src/tests/anim_test.py &
  wait
fi
summary
