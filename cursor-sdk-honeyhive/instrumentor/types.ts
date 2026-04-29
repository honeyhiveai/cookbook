import { type ConversationStep, type RunResult, type RunResultStatus, type SDKAgent } from '@cursor/sdk';
import { type AddSessionTracesRequest } from '@honeyhive/api-client';

export type HoneyHiveTraceEvent = AddSessionTracesRequest['logs'][number];
export type CursorRunGit = RunResult['git'];
export type SanitizeContext =
  | 'prompt'
  | 'result'
  | 'thinking'
  | 'toolArgs'
  | 'toolResult'
  | 'metadata'
  | 'workspace';

export type HoneyHiveSanitizer = (value: unknown, context: SanitizeContext) => unknown;
export type ToolConversationStep = Extract<ConversationStep, { type: 'toolCall' }>;

export interface HoneyHiveCursorInstrumentorOptions {
  apiKey?: string;
  project?: string;
  source?: string;
  serverUrl?: string;
  sanitize?: HoneyHiveSanitizer;
}

export interface TraceCursorRunOptions {
  agent: SDKAgent;
  message: string;
  sessionName?: string;
  model?: string;
  cwd?: string;
}

export interface TraceCursorRunResult {
  cursorAgentId: string;
  cursorRunId: string;
  cursorStatus: RunResultStatus;
  honeyhiveSessionId: string;
  honeyhiveEventId: string;
  exportedEvents: number;
  toolEvents: number;
}
