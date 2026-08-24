#!/bin/bash
# Pin many Salesforce session IDs after a wrong-project pass.
# Run from this directory after sourcing poller.env.
# Set SAME_ORG=1 when the wrong and right HoneyHive projects share an org.
# Set SAME_ORG=0 when they do not.
set -o pipefail
export PYTHONUNBUFFERED=1
status=0
echo "=== attempt $(date -u +%FT%TZ) SAME_ORG=${SAME_ORG:-unset} ===" >> agentforce-repin.log
say() { echo "$@" | tee -a agentforce-repin.log; }
case "${SAME_ORG:-}" in
  1|0) say "SAME_ORG=$SAME_ORG" ;;
  *) say "Set SAME_ORG=1 (same org) or SAME_ORG=0 (different orgs)"; status=1 ;;
esac
if [ "${SAME_ORG:-}" = 1 ] || [ "${SAME_ORG:-}" = 0 ]; then
  if [ -s ids.remaining.txt ]; then
    say "ids.remaining.txt is non-empty: the last attempt hit a bound and stopped. Rebuild ids.txt from OPERATING.md, then check the first ID before you re-run. Do not run 'mv ids.remaining.txt ids.txt'"
    status=1
  elif [ -s ids.done.txt ]; then
    say "ids.done.txt is non-empty: the last attempt was interrupted, or a bound stop was only half-recovered. Rebuild ids.txt from OPERATING.md. Deleting ids.done.txt without rebuilding re-pins every ID already walked"
    status=1
  elif [ ! -f ids.txt ]; then
    say "ids.txt is missing"; status=1
  elif [ -s ids.dedup.txt ] && tr -d '\r' < ids.txt | awk 'NF && !seen[$0]++' | cmp -s - ids.dedup.txt; then
    say "ids.txt matches ids.dedup.txt, the list the last campaign walked. See After the pins in OPERATING.md"
    status=1
  else
  tr -d '\r' < ids.txt | awk 'NF && !seen[$0]++' > ids.next.txt
  if [ ! -s ids.next.txt ]; then
    say "ids.txt has no usable IDs; ids.dedup.txt left as it was"; rm -f ids.next.txt; status=1
  else
  mv ids.next.txt ids.dedup.txt
  : > ids.remaining.txt
  fails=0
  total=0
  stop=0
  { while read -r id || [ -n "$id" ]; do
    id="${id%$'\r'}"
    [ -n "$id" ] || continue
    if [ "$stop" -eq 1 ]; then
      echo "$id" >> ids.remaining.txt
      echo "$id"
      continue
    fi
    if [ "$SAME_ORG" = 1 ]; then
      hh=$(python3 -c "import uuid; print(uuid.uuid4())") || hh=""
      if [ -z "$hh" ]; then
        echo "Could not mint a UUID; stopping at $id"
        stop=1
        echo "Unprocessed IDs (this one and after):"
        echo "$id" >> ids.remaining.txt
        echo "$id"
        continue
      fi
      if ! SALESFORCE_SESSION_ID="$id" \
        HONEYHIVE_SESSION_ID="$hh" \
        HONEYHIVE_SESSION_NAME= \
        DRY_RUN= \
        MAX_PASSES=1 python3 poll_agentforce.py < /dev/null
      then
        fails=$((fails + 1))
        total=$((total + 1))
        if [ "$fails" -ge 3 ] || [ "$total" -ge 10 ]; then
          stop=1
          echo "Stopping after too many failures (three consecutive or ten total). Unprocessed IDs (this one and after):"
          echo "$id" >> ids.remaining.txt
          echo "$id"
        else
          echo "$id" >> ids.done.txt
        fi
      else
        fails=0
        echo "$id" >> ids.done.txt
      fi
    elif ! HONEYHIVE_SESSION_ID= \
      HONEYHIVE_SESSION_NAME= \
      DRY_RUN= \
      SALESFORCE_SESSION_ID="$id" \
      MAX_PASSES=1 python3 poll_agentforce.py < /dev/null
    then
      fails=$((fails + 1))
      total=$((total + 1))
      if [ "$fails" -ge 3 ] || [ "$total" -ge 10 ]; then
        stop=1
        echo "Stopping after too many failures (three consecutive or ten total). Unprocessed IDs (this one and after):"
        echo "$id" >> ids.remaining.txt
        echo "$id"
      else
        echo "$id" >> ids.done.txt
      fi
    else
      fails=0
      echo "$id" >> ids.done.txt
    fi
    done
    [ "$stop" -eq 1 ] || {
      rm -f ids.done.txt ids.txt
      echo "Campaign finished: removed ids.txt so a re-run cannot re-pin. A later run exits with ids.txt is missing."
    }
    [ "$stop" -eq 0 ]
  } < ids.dedup.txt 2>&1 | tee -a agentforce-repin.log
  [ "$?" -eq 0 ] || status=1
  fi
  fi
fi
exit "$status"
