import crypto from 'node:crypto';

import { type RunResultStatus } from '@cursor/sdk';
import { Client, type StartSessionResponse } from '@honeyhive/api-client';

import { createClientConfig } from './config.js';
import { createAgentEvent, createFinalEvent, createToolEvent } from './events.js';
import {
  type CursorRunGit,
  type HoneyHiveSanitizer,
  type HoneyHiveCursorInstrumentorOptions,
  type HoneyHiveTraceEvent,
  type TraceCursorRunOptions,
  type TraceCursorRunResult,
} from './types.js';
import { compactObject, defaultSanitize, formatError, isString } from './utils.js';

export class HoneyHiveCursorInstrumentor {
  #client: Client;
  #project?: string;
  #source: string;
  #sanitize: HoneyHiveSanitizer;

  constructor(options: HoneyHiveCursorInstrumentorOptions = {}) {
    this.#client = new Client(createClientConfig(options));
    this.#project = options.project;
    this.#source = options.source ?? 'cursor-sdk-demo';
    this.#sanitize = options.sanitize ?? defaultSanitize;
  }

  async traceRun(options: TraceCursorRunOptions): Promise<TraceCursorRunResult> {
    const sessionId = crypto.randomUUID();
    const agentEventId = crypto.randomUUID();
    const finalEventId = crypto.randomUUID();
    const startTime = Date.now();

    let cursorRunId = '';
    let status: RunResultStatus = 'error';
    let resultText: string | undefined;
    let durationMs: number | undefined;
    let git: CursorRunGit | undefined;
    let error: string | undefined;
    let finalAssistantText = '';
    let thinkingText = '';
    const stepCounts: Record<string, number> = {};
    const toolEvents: HoneyHiveTraceEvent[] = [];

    try {
      const run = await options.agent.send(options.message, {
        onStep: ({ step }) => {
          stepCounts[step.type] = (stepCounts[step.type] ?? 0) + 1;

          switch (step.type) {
            case 'thinkingMessage':
              thinkingText += step.message.text;
              break;
            case 'assistantMessage':
              finalAssistantText += step.message.text;
              break;
            case 'toolCall':
              toolEvents.push(
                createToolEvent({
                  step,
                  sessionId,
                  parentId: agentEventId,
                  project: this.#project,
                  source: this.#source,
                  thinkingText,
                  sanitize: this.#sanitize,
                }),
              );
              thinkingText = '';
              break;
            default: {
              const exhaustive: never = step;
              throw new Error(`Unhandled Cursor conversation step: ${JSON.stringify(exhaustive)}`);
            }
          }
        },
      });
      cursorRunId = run.id;

      const result = await run.wait();
      status = result.status;
      resultText = result.result;
      durationMs = result.durationMs;
      git = result.git;
    } catch (caught) {
      error = formatError(caught);
      status = 'error';
    }

    const endTime = Date.now();
    const result = resultText ?? finalAssistantText;
    const exportedEvents = [
      createAgentEvent({
        eventId: agentEventId,
        sessionId,
        parentId: sessionId,
        childrenIds: toolEvents.map((event) => event.event_id).filter(isString),
        project: this.#project,
        source: this.#source,
        agentId: options.agent.agentId,
        runId: cursorRunId,
        model: options.model,
        cwd: options.cwd,
        prompt: options.message,
        result,
        status,
        error,
        startTime,
        endTime,
        durationMs,
        git,
        stepCounts,
        thinkingText,
        sanitize: this.#sanitize,
      }),
      ...toolEvents,
      createFinalEvent({
        eventId: finalEventId,
        sessionId,
        parentId: sessionId,
        project: this.#project,
        source: this.#source,
        model: options.model,
        prompt: options.message,
        result,
        status,
        error,
        endTime,
        sanitize: this.#sanitize,
      }),
    ];

    const session = await this.#startSession({
      sessionId,
      sessionName: options.sessionName ?? 'Cursor SDK HoneyHive Demo',
      prompt: options.message,
      cwd: options.cwd,
      result,
      status,
      error,
      startTime,
      endTime,
      childrenIds: [agentEventId, finalEventId],
    });
    await this.#client.sessions.addTraces({
      path: { session_id: sessionId },
      body: { logs: exportedEvents },
    });

    return {
      cursorAgentId: options.agent.agentId,
      cursorRunId,
      cursorStatus: status,
      honeyhiveSessionId: sessionId,
      honeyhiveEventId: session.event_id,
      exportedEvents: exportedEvents.length + 1,
      toolEvents: toolEvents.length,
    };
  }

  async #startSession(options: {
    sessionId: string;
    sessionName: string;
    prompt: string;
    cwd?: string;
    result?: string;
    status: RunResultStatus;
    error?: string;
    startTime: number;
    endTime: number;
    childrenIds: string[];
  }): Promise<StartSessionResponse> {
    return this.#client.sessions.start({
      body: {
        session: {
          session_id: options.sessionId,
          session_name: options.sessionName,
          event_name: 'session.start',
          source: this.#source,
          start_time: options.startTime,
          end_time: options.endTime,
          duration: options.endTime - options.startTime,
          inputs: compactObject({
            prompt: options.prompt,
            workspace: this.#sanitize(options.cwd, 'workspace'),
          }),
          outputs: compactObject({
            status: options.status,
            result: this.#sanitize(options.result, 'result'),
          }),
          metadata: compactObject({
            project: this.#project,
            error: options.error,
            sdk: 'cursor',
          }),
          children_ids: options.childrenIds,
        },
      },
    });
  }

}
