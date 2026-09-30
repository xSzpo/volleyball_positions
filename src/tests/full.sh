#!/usr/bin/env bash
# Once per ticket, after review fixes: build and audit, then every browser test in parallel.
source "$(dirname "$0")/lib.sh"

ORDER=(build audit qa-m qa-d theme analytics flags match mp online)
run build src/build.py
run audit src/tests/audit.py
read -r rc _ <"$LOGS/build.status"
if [ "$rc" = 0 ]; then
  run qa-m src/tests/qa.py m &
  run qa-d src/tests/qa.py d --quick &
  run match src/tests/match_test.py &
  run mp src/tests/mp_test.py &
  run online src/tests/online_test.py &
  {
    run theme src/tests/theme_test.py
    run analytics src/tests/analytics_test.py
    run flags src/tests/flags_test.py
  } &
  wait
fi
summary
