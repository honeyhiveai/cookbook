# Instrumentation success criteria

Phase 2 of [`SKILL.md`](SKILL.md) has two steps: (1) a mechanical smoke run that confirms the process exits clean and a session lands at HoneyHive, then (2) **grading the resulting trace against this rubric**. A mechanically-correct integration that produces a messy trace is not done. This page is what step 2 grades against — what a well-instrumented trace should actually look like once spans are flowing.

A well-instrumented trace has:

## An easy-to-debug trace structure

- Event names are meaningful and easy to navigate — agent names, tool names are present in the event name itself.
- The order in which the events show up follows time-based order.
- An agent's LLM calls & tool calls are nested within a clear agent event.
- LLM calls are easy to find & not deeply hidden.
- Event types are colored in an easy-to-understand way.
- Any agent-to-agent interactions have a clear handoff / tool event.
- Tool calls aren't nested weirdly & are easy to link to the originating LLM / agent call.

## A clean input-output state on core events

- Core orchestration events clearly show what was accepted and what was returned.
- User's original query & follow-up queries are easy to identify.
- LLM calls show the full message history, tool list & response cleanly.
- Tool calls show what the LLM's inputs were & the final tool response returned.
- Agent invocation shows what the query was and the final plan / trajectory it took.
- Agent handoff events clearly show what context was passed ahead.

## Visible semantic failures

- Any problematic steps in a long-running agent / RAG are highlighted.
- Any guardrail triggers are identified easily.
- Any human interventions are identified easily.

## An end-to-end session summary

- There exists some event in the trace (the final LLM call, etc.) that has a sufficiently good summary of the whole trace to set up end-to-end evaluators against.
