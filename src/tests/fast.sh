#!/usr/bin/env bash
# Iteration loop: build, data audit, theme, analytics and flag tests and the quick phone sweep. Stops at the first failure.
source "$(dirname "$0")/lib.sh"

for step in "build src/build.py" "audit src/tests/audit.py" "theme src/tests/theme_test.py" \
  "analytics src/tests/analytics_test.py" "flags src/tests/flags_test.py" "qa-quick src/tests/qa.py m --quick"; do
  set -- $step
  ORDER+=("$1")
  run "$@" || true
  read -r rc _ <"$LOGS/$1.status"
  [ "$rc" = 0 ] || break
done
summary
