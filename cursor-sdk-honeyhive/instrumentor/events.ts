import crypto from 'node:crypto';

import { type RunResultStatus } from '@cursor/sdk';

import {
  getToolArgs,
  getToolExecutionTimeMs,
  getToolResult,
  getToolResultStatus,
} from './cursorSteps.js';
import {
  type CursorConversationSummary,
  type CursorDeltaSummary,
  type CursorRunGit,
  type CursorStreamSummary,
  type CursorTokenUsage,
  type HoneyHiveSanitizer,
  type HoneyHiveTraceEvent,
  type ToolConversationStep,
} from './types.js';
import { compact, compactObject, sanitizeRecord } from './utils.js';

export function createToolEvent(options: {
  step: ToolConversationStep;
  sessionId: string;
  parentId: string;
  project?: string;
  source: string;
  thinkingText: string;
  sanitize: HoneyHiveSanitizer;
}): HoneyHiveTraceEvent {
  const now = Date.now();
  const tool = options.step.message;
  const resultStatus = getToolResultStatus(tool);
  const executionTime = getToolExecutionTimeMs(tool);
  const result = getToolResult(tool);

  return {
    event_id: crypto.randomUUID(),
    session_id: options.sessionId,
    parent_id: options.parentId,
    event_type: 'tool',
    event_name: `tool.${tool.type}`,
    source: options.source,
    start_time: executionTime === undefined ? now : now - executionTime,
    end_time: now,
    duration: executionTime,
    inputs: sanitizeRecord(
      {
        args: getToolArgs(tool),
        thinking: options.thinkingText || undefined,
      },
      options.sanitize,
      'toolArgs',
    ),
    outputs: sanitizeRecord({ result }, options.sanitize, 'toolResult'),
    error: resultStatus === 'error' ? compact(result) : undefined,
    metadata: compactObject({
      project: options.project,
      'gen_ai.system': 'cursor',
      'gen_ai.operation.name': 'execute_tool',
      'gen_ai.tool.name': tool.type,
      'cursor.tool.status': resultStatus,
    }),
  };
}

export function createAgentEvent(options: {
  eventId: string;
  sessionId: string;
  parentId: string;
  childrenIds: string[];
  project?: string;
  source: string;
  agentId: string;
  runId: string;
  model?: string;
  cwd?: string;
  prompt: string;
  result?: string;
  status: RunResultStatus;
  error?: string;
  startTime: number;
  endTime: number;
  durationMs?: number;
  git?: CursorRunGit;
  stepCounts: Record<string, number>;
  deltaSummary: CursorDeltaSummary;
  streamSummary: CursorStreamSummary;
  streamError?: string;
  conversationSummary?: CursorConversationSummary;
  conversationError?: string;
  thinkingText: string;
  sanitize: HoneyHiveSanitizer;
}): HoneyHiveTraceEvent {
  return {
    event_id: options.eventId,
    session_id: options.sessionId,
    parent_id: options.parentId,
    children_ids: options.childrenIds,
    event_type: 'chain',
    event_name: 'agent.run',
    source: options.source,
    start_time: options.startTime,
    end_time: options.endTime,
    duration: options.durationMs ?? options.endTime - options.startTime,
    config: compactObject({
      model: options.model,
      'gen_ai.system': 'cursor',
      'gen_ai.operation.name': 'invoke_agent',
      'gen_ai.agent.name': 'Cursor SDK Agent',
    }),
    metrics: compactObject({
      token_delta_total: options.deltaSummary.tokenDeltaTotal,
      step_duration_ms_total: sum(options.deltaSummary.stepDurationsMs),
      thinking_duration_ms_total: sum(options.deltaSummary.thinkingDurationsMs),
    }),
    inputs: compactObject({
      prompt: options.prompt,
      workspace: options.sanitize(options.cwd, 'workspace'),
    }),
    outputs: compactObject({
      status: options.status,
      result: options.sanitize(options.result, 'result'),
      thinking: options.sanitize(options.thinkingText, 'thinking'),
    }),
    error: eventError(options.status, options.error),
    metadata: compactObject({
      project: options.project,
      'cursor.agent_id': options.agentId,
      'cursor.run_id': options.runId,
      'cursor.runtime': 'local',
      'cursor.git': options.sanitize(options.git, 'metadata'),
      'cursor.step_counts': options.stepCounts,
      'cursor.delta_counts': options.deltaSummary.counts,
      'cursor.stream': options.streamSummary,
      'cursor.stream_error': options.streamError,
      'cursor.step_durations_ms': options.deltaSummary.stepDurationsMs.length
        ? options.deltaSummary.stepDurationsMs
        : undefined,
      'cursor.thinking_durations_ms': options.deltaSummary.thinkingDurationsMs.length
        ? options.deltaSummary.thinkingDurationsMs
        : undefined,
      'cursor.shell_output_chunks': options.deltaSummary.shellOutputChunks || undefined,
      'cursor.summary_updates': options.deltaSummary.summaryUpdates || undefined,
      'cursor.conversation': options.conversationSummary,
      'cursor.conversation_error': options.conversationError,
    }),
  };
}

export function createFinalEvent(options: {
  eventId: string;
  sessionId: string;
  parentId: string;
  project?: string;
  source: string;
  model?: string;
  prompt: string;
  result?: string;
  status: RunResultStatus;
  error?: string;
  startTime: number;
  endTime: number;
  usage?: CursorTokenUsage;
  sanitize: HoneyHiveSanitizer;
}): HoneyHiveTraceEvent {
  const usageFields = tokenUsageFields(options.usage);
  const startTime = options.startTime;

  return {
    event_id: options.eventId,
    session_id: options.sessionId,
    parent_id: options.parentId,
    event_type: 'model',
    event_name: 'turn.agent',
    source: options.source,
    start_time: startTime,
    end_time: options.endTime,
    duration: options.endTime - startTime,
    config: compactObject({
      model: options.model,
      provider: 'cursor',
      'gen_ai.system': 'cursor',
      'gen_ai.operation.name': 'chat',
    }),
    inputs: compactObject({
      chat_history: [{ role: 'user', content: options.sanitize(options.prompt, 'prompt') }],
    }),
    outputs: compactObject({
      role: 'assistant',
      content: options.sanitize(options.result, 'result'),
      status: options.status,
    }),
    error: eventError(options.status, options.error),
    metadata: compactObject({
      project: options.project,
      provider: 'cursor',
      ...usageFields,
    }),
  };
}

function eventError(cursorStatus: RunResultStatus, error?: string): string | undefined {
  if (error) {
    return error;
  }
  if (cursorStatus === 'finished') {
    return undefined;
  }
  return `Cursor run ${cursorStatus}`;
}

function tokenUsageFields(usage?: CursorTokenUsage): Record<string, number> {
  if (!usage) {
    return {};
  }

  return {
    prompt_tokens: usage.inputTokens,
    completion_tokens: usage.outputTokens,
    total_tokens: usage.inputTokens + usage.outputTokens,
    cache_read_input_tokens: usage.cacheReadTokens,
    cache_write_input_tokens: usage.cacheWriteTokens,
  };
}

function sum(values: number[]): number | undefined {
  if (!values.length) {
    return undefined;
  }
  return values.reduce((total, value) => total + value, 0);
}
