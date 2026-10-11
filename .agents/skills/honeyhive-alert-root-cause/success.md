# Alert investigation success criteria

[`SKILL.md`](SKILL.md) defines the investigation workflow. This page is the rubric for grading whether an investigation was thorough and actionable. A mechanically-correct query that misclassifies findings or produces vague recommendations is not done.

A well-executed alert investigation has:

## Correct URL decoding

- The base64 config was decoded without errors.
- All fields were extracted: type, filters, metric, func, dateRange, bucketing.
- The trigger condition was derived correctly (metric + threshold filter).
- The alert context summary matches the decoded config — no fields dropped or misinterpreted.

## Accurate session querying

- Filters match the alert config (metric filter, event_type, any additional filters from the URL).
- dateRange was passed as a top-level field, not inside the filters array.
- Filter types are correct (string, number, boolean, datetime — not float or int).
- All matching sessions were retrieved (pagination handled if results exceed one page).

## Complete trace tree walking

- Every flagged session had its child events fetched (limit 500, not truncated at default).
- The event tree was walked to leaf events — not just the session root.
- Tool events had their inputs/outputs inspected for the monitored pattern.
- Surrounding events were checked to understand the context that led to the flagged behavior.
- Session-level metadata was noted for context.

## Accurate classification

- Each finding is classified as true positive or false positive with evidence.
- String-literal false positives are correctly identified: patterns that appear inside generated content, evaluator definitions, or test fixtures are not flagged as executed behavior.
- Severity levels are calibrated relative to the actual risk (destructive + irreversible = critical, scoped + recoverable = low).
- The classification distinguishes between the agent performing a flagged action vs. producing output that contains the flagged pattern.

## Actionable recommendations

- Recommendations are specific: exact hook patterns, evaluator regex changes, or prompt additions — not generic advice.
- False-positive reduction suggestions target the specific pattern that caused the misclassification.
- Guardrail recommendations include both blocking (pre-execution hooks) and detection (evaluator refinements).
- Whitelist suggestions are scoped narrowly to the safe variant identified, not broad exclusions.
