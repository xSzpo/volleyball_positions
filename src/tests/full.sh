#!/usr/bin/env bash
# Once per ticket, after review fixes: build and audit, then every browser test in parallel.
source "$(dirname "$0")/lib.sh"

ORDER=(build audit qa-m qa-d theme analytics flags rules learn anim match mp online report)
run build src/build.py
run audit src/tests/audit.py
read -r rc _ <"$LOGS/build.status"
if [ "$rc" = 0 ]; then
  run qa-m src/tests/qa.py m &
  run qa-d src/tests/qa.py d --quick &
  run match src/tests/match_test.py &
  run mp src/tests/mp_test.py &
  # Both use the emulator ports 9000 and 9099, so they run one after the other.
  {
    run online src/tests/online_test.py
    run report src/tests/report_test.py
  } &
  {
    run theme src/tests/theme_test.py
    run analytics src/tests/analytics_test.py
    run flags src/tests/flags_test.py
    run rules src/tests/rules_test.py
    run learn src/tests/learn_test.py
    run anim src/tests/anim_test.py
  } &
  wait
fi
summary
