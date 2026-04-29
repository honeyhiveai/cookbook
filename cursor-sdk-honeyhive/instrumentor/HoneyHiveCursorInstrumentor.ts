import crypto from 'node:crypto';

import {
  type ConversationTurn,
  type InteractionUpdate,
  type ModelSelection,
  type RunResultStatus,
  type SDKMessage,
} from '@cursor/sdk';
import { Client, type StartSessionResponse } from '@honeyhive/api-client';

import { createClientConfig } from './config.js';
import { createAgentEvent, createFinalEvent, createToolEvent } from './events.js';
import {
  type CursorConversationSummary,
  type CursorDeltaSummary,
  type CursorMessageInput,
  type CursorRunGit,
  type CursorStreamSummary,
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
    const deltaSummary = createDeltaSummary();
    const streamSummary = createStreamSummary();
    let streamError: string | undefined;
    let conversationSummary: CursorConversationSummary | undefined;
    let conversationError: string | undefined;
    const promptText = messageText(options.message);
    let resolvedModel = options.model ?? modelSelectionName(options.sendOptions?.model);

    try {
      const run = await options.agent.send(options.message, {
        ...options.sendOptions,
        onDelta: async ({ update }) => {
          recordDelta(deltaSummary, update);
          await options.onDelta?.(update);
        },
        onStep: async ({ step }) => {
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

          await options.onStep?.(step);
        },
      });
      cursorRunId = run.id;

      if (run.supports('stream')) {
        try {
          for await (const event of run.stream()) {
            recordStream(streamSummary, event);
            if (event.type === 'system') {
              resolvedModel = modelSelectionName(event.model) ?? resolvedModel;
            }
            await options.onStream?.(event);
          }
        } catch (caught) {
          streamError = formatError(caught);
        }
      } else {
        streamError = run.unsupportedReason('stream');
      }

      const result = await run.wait();
      status = result.status;
      resultText = result.result;
      durationMs = result.durationMs;
      git = result.git;
      resolvedModel = modelSelectionName(result.model) ?? resolvedModel;

      if (run.supports('conversation')) {
        try {
          conversationSummary = summarizeConversation(await run.conversation());
        } catch (caught) {
          conversationError = formatError(caught);
        }
      } else {
        conversationError = run.unsupportedReason('conversation');
      }
    } catch (caught) {
      error = formatError(caught);
      status = 'error';
    }

    const endTime = Date.now();
    const result = resultText ?? finalAssistantText;
    const agentChildrenIds = [
      ...toolEvents.map((event) => event.event_id).filter(isString),
      finalEventId,
    ];
    const exportedEvents = [
      createAgentEvent({
        eventId: agentEventId,
        sessionId,
        parentId: sessionId,
        childrenIds: agentChildrenIds,
        project: this.#project,
        source: this.#source,
        agentId: options.agent.agentId,
        runId: cursorRunId,
        model: resolvedModel,
        cwd: options.cwd,
        prompt: promptText,
        result,
        status,
        error,
        startTime,
        endTime,
        durationMs,
        git,
        stepCounts,
        deltaSummary,
        streamSummary,
        streamError,
        conversationSummary,
        conversationError,
        thinkingText,
        sanitize: this.#sanitize,
      }),
      ...toolEvents,
      createFinalEvent({
        eventId: finalEventId,
        sessionId,
        parentId: agentEventId,
        project: this.#project,
        source: this.#source,
        model: resolvedModel,
        prompt: promptText,
        result,
        status,
        error,
        startTime: deltaSummary.responseStartTime ?? endTime,
        endTime,
        usage: deltaSummary.usage,
        sanitize: this.#sanitize,
      }),
    ];

    const session = await this.#startSession({
      sessionId,
      sessionName: options.sessionName ?? 'Cursor SDK HoneyHive Demo',
      prompt: promptText,
      cwd: options.cwd,
      result,
      status,
      error,
      startTime,
      endTime,
      childrenIds: [agentEventId],
      usage: deltaSummary.usage,
      conversationSummary,
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
    usage?: CursorDeltaSummary['usage'];
    conversationSummary?: CursorConversationSummary;
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
            conversation: options.conversationSummary,
          }),
          children_ids: options.childrenIds,
        },
      },
    });
  }

}

function createDeltaSummary(): CursorDeltaSummary {
  return {
    counts: {},
    stepDurationsMs: [],
    thinkingDurationsMs: [],
    shellOutputChunks: 0,
    summaryUpdates: 0,
  };
}

function createStreamSummary(): CursorStreamSummary {
  return {
    counts: {},
    statuses: [],
    taskUpdates: 0,
    requests: 0,
    toolCalls: {},
  };
}

function recordStream(summary: CursorStreamSummary, event: SDKMessage): void {
  summary.counts[event.type] = (summary.counts[event.type] ?? 0) + 1;

  switch (event.type) {
    case 'system':
      summary.tools = event.tools;
      break;
    case 'tool_call': {
      const toolStatuses = summary.toolCalls[event.name] ?? {};
      toolStatuses[event.status] = (toolStatuses[event.status] ?? 0) + 1;
      summary.toolCalls[event.name] = toolStatuses;
      break;
    }
    case 'status':
      summary.statuses.push(event.status);
      break;
    case 'task':
      summary.taskUpdates += 1;
      break;
    case 'request':
      summary.requests += 1;
      break;
    case 'user':
    case 'assistant':
    case 'thinking':
      break;
  }
}

function recordDelta(summary: CursorDeltaSummary, update: InteractionUpdate): void {
  summary.counts[update.type] = (summary.counts[update.type] ?? 0) + 1;

  switch (update.type) {
    case 'text-delta':
      summary.responseStartTime ??= Date.now();
      break;
    case 'turn-ended':
      summary.usage = mergeUsage(summary.usage, update.usage);
      break;
    case 'token-delta':
      summary.tokenDeltaTotal = (summary.tokenDeltaTotal ?? 0) + update.tokens;
      break;
    case 'step-completed':
      summary.stepDurationsMs.push(update.stepDurationMs);
      break;
    case 'thinking-completed':
      summary.thinkingDurationsMs.push(update.thinkingDurationMs);
      break;
    case 'shell-output-delta':
      summary.shellOutputChunks += 1;
      break;
    case 'summary':
    case 'summary-started':
    case 'summary-completed':
      summary.summaryUpdates += 1;
      break;
    case 'thinking-delta':
    case 'tool-call-started':
    case 'partial-tool-call':
    case 'tool-call-completed':
    case 'step-started':
    case 'user-message-appended':
      break;
  }
}

function mergeUsage(
  current: CursorDeltaSummary['usage'],
  next: CursorDeltaSummary['usage'],
): CursorDeltaSummary['usage'] {
  if (!next) {
    return current;
  }
  if (!current) {
    return next;
  }
  return {
    inputTokens: current.inputTokens + next.inputTokens,
    outputTokens: current.outputTokens + next.outputTokens,
    cacheReadTokens: current.cacheReadTokens + next.cacheReadTokens,
    cacheWriteTokens: current.cacheWriteTokens + next.cacheWriteTokens,
  };
}

function summarizeConversation(turns: ConversationTurn[]): CursorConversationSummary {
  const summary: CursorConversationSummary = {
    turns: turns.length,
    agentTurns: 0,
    shellTurns: 0,
    stepCounts: {},
    shellCommands: 0,
    shellOutputs: 0,
  };

  for (const conversationTurn of turns) {
    switch (conversationTurn.type) {
      case 'agentConversationTurn':
        summary.agentTurns += 1;
        for (const step of conversationTurn.turn.steps) {
          summary.stepCounts[step.type] = (summary.stepCounts[step.type] ?? 0) + 1;
        }
        break;
      case 'shellConversationTurn':
        summary.shellTurns += 1;
        if (conversationTurn.turn.shellCommand) {
          summary.shellCommands += 1;
        }
        if (conversationTurn.turn.shellOutput) {
          summary.shellOutputs += 1;
        }
        break;
    }
  }

  return summary;
}

function messageText(message: CursorMessageInput): string {
  return typeof message === 'string' ? message : message.text;
}

function modelSelectionName(model?: ModelSelection): string | undefined {
  if (!model) {
    return undefined;
  }
  if (!model.params?.length) {
    return model.id;
  }
  const params = model.params.map((param) => `${param.id}=${param.value}`).join(',');
  return `${model.id}(${params})`;
}
