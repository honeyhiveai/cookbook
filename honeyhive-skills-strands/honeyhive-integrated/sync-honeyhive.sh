#!/usr/bin/env bash
# Sync .honeyhive/ resources to HoneyHive via the CLI.
# Usage: HH_API_KEY=... bash sync-honeyhive.sh
#
# See https://docs.honeyhive.ai/v2/sdk-reference/cli-config-as-code
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="$ROOT/.honeyhive/state.json"
DATASET_FILE="$ROOT/.honeyhive/datasets/strands-skills-eval.yaml"

if ! command -v honeyhive >/dev/null 2>&1; then
  echo "HoneyHive CLI not found. Install: brew tap honeyhiveai/tap && brew install honeyhive" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for sync-honeyhive.sh" >&2
  exit 1
fi

[ -f "$STATE_FILE" ] || echo '{"evaluators":{},"datapoints":{},"datasets":{}}' > "$STATE_FILE"

for file in "$ROOT"/.honeyhive/evaluators/*.yaml; do
  [ -f "$file" ] || continue
  name="$(grep '^name:' "$file" | awk '{print $2}')"
  existing_id="$(jq -r --arg n "$name" '.evaluators[$n] // ""' "$STATE_FILE")"

  if [ -n "$existing_id" ]; then
    tmp="$(mktemp).yaml"
    { echo "metric_id: $existing_id"; cat "$file"; } > "$tmp"
    honeyhive metrics update --filename "$tmp" >/dev/null
    rm -f "$tmp"
    echo "Updated evaluator $name ($existing_id)"
  else
    new_id="$(honeyhive metrics create --filename "$file" | jq -r '.metric_id')"
    jq --arg n "$name" --arg id "$new_id" '.evaluators[$n] = $id' "$STATE_FILE" > "${STATE_FILE}.tmp"
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
    echo "Created evaluator $name ($new_id)"
  fi
done

dataset_name="$(grep '^name:' "$DATASET_FILE" | awk '{print $2}')"
dataset_id="$(jq -r --arg n "$dataset_name" '.datasets[$n] // ""' "$STATE_FILE")"

if [ -z "$dataset_id" ]; then
  dataset_id="$(honeyhive datasets create --filename "$DATASET_FILE" | jq -r '.result.insertedId')"
  jq --arg n "$dataset_name" --arg id "$dataset_id" '.datasets[$n] = $id' "$STATE_FILE" > "${STATE_FILE}.tmp"
  mv "${STATE_FILE}.tmp" "$STATE_FILE"
  echo "Created dataset $dataset_name ($dataset_id)"
else
  echo "Dataset $dataset_name already synced ($dataset_id)"
fi

for file in "$ROOT"/.honeyhive/datapoints/*.yaml; do
  [ -f "$file" ] || continue
  external_id="$(grep 'external_id:' "$file" | head -1 | awk '{print $2}')"
  existing_id="$(jq -r --arg id "$external_id" '.datapoints[$id] // ""' "$STATE_FILE")"

  tmp="$(mktemp).yaml"
  if [ -n "$existing_id" ]; then
    echo "datapoint_id: $existing_id" > "$tmp"
  fi
  cat "$file" >> "$tmp"
  {
    echo "linked_datasets:"
    echo "  - \"$dataset_id\""
  } >> "$tmp"

  if [ -n "$existing_id" ]; then
    honeyhive datapoints update --filename "$tmp" >/dev/null
    rm -f "$tmp"
    echo "Updated datapoint $external_id ($existing_id)"
  else
    new_id="$(honeyhive datapoints create --filename "$tmp" | jq -r '.result.insertedIds[0]')"
    rm -f "$tmp"
    jq --arg id "$external_id" --arg dp "$new_id" '.datapoints[$id] = $dp' "$STATE_FILE" > "${STATE_FILE}.tmp"
    mv "${STATE_FILE}.tmp" "$STATE_FILE"
    echo "Created datapoint $external_id ($new_id)"
  fi
done

echo "Sync complete. State: $STATE_FILE"
