# State specification

Each phase writes its output to a JSON file under `state/` (relative to the `honeyhive-instrument/` root). These files are the handoff contract between phases — each phase reads its predecessor's state rather than re-detecting.

Schemas are JSON Schema (draft 2020-12) in [`state-specs/`](../state-specs/).

## Files

| State file | Written by | Read by | Schema |
|---|---|---|---|
| `state/network-validation.json` | Prerequisite (honeyhive-cli sanity check) | Runtime validation, Phase 1 | [state-specs/network-validation.json](../state-specs/network-validation.json) |
| `state/runtime-validation.json` | Phase 0 (runtime validation) | Phase 1 setup | [state-specs/runtime-validation.json](../state-specs/runtime-validation.json) |
| `state/setup-result.json` | Phase 1 (language-specific setup) | Phase 2 verification | [state-specs/setup-result.json](../state-specs/setup-result.json) |
| `state/trace-grade.json` | Phase 2 (verification) | Stop/continue decision, downstream skills | [state-specs/trace-grade.json](../state-specs/trace-grade.json) |

## Lifecycle

1. Prerequisite writes `state/network-validation.json`. On `"status": "fail"`, skill stops.
2. Phase 0 reads network-validation, writes `state/runtime-validation.json`. On conflicts, surfaces to user.
3. Phase 1 reads both Phase 0 state files, writes `state/setup-result.json`.
4. Phase 2 reads setup-result, writes `state/trace-grade.json`. On `"grade": "pass"`, skill proceeds to stop.

Each file is overwritten on re-run (not appended). The timestamp field tracks currency.

Create the state directory on first write: `mkdir -p state`.
