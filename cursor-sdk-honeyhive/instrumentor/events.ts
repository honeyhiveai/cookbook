import crypto from 'node:crypto';

import { type RunResultStatus } from '@cursor/sdk';

import {
  getToolArgs,
  getToolExecutionTimeMs,
  getToolResult,
  getToolResultStatus,
} from './cursorSteps.js';
import {
  type CursorRunGit,
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
  endTime: number;
  sanitize: HoneyHiveSanitizer;
}): HoneyHiveTraceEvent {
  return {
    event_id: options.eventId,
    session_id: options.sessionId,
    parent_id: options.parentId,
    event_type: 'model',
    event_name: 'turn.agent',
    source: options.source,
    start_time: options.endTime,
    end_time: options.endTime,
    duration: 0,
    config: compactObject({
      model: options.model,
      'gen_ai.system': 'cursor',
      'gen_ai.operation.name': 'chat',
    }),
    inputs: {
      prompt: options.sanitize(options.prompt, 'prompt'),
    },
    outputs: compactObject({
      status: options.status,
      response: options.sanitize(options.result, 'result'),
    }),
    error: eventError(options.status, options.error),
    metadata: compactObject({
      project: options.project,
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
