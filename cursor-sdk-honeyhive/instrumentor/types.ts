import {
  type ConversationStep,
  type InteractionUpdate,
  type RunResult,
  type RunResultStatus,
  type SDKAgent,
  type SDKMessage,
  type SDKUserMessage,
  type SendOptions,
} from '@cursor/sdk';
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
export type CursorMessageInput = string | SDKUserMessage;

export interface CursorTokenUsage {
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheWriteTokens: number;
}

export interface CursorDeltaSummary {
  counts: Record<string, number>;
  usage?: CursorTokenUsage;
  tokenDeltaTotal?: number;
  responseStartTime?: number;
  stepDurationsMs: number[];
  thinkingDurationsMs: number[];
  shellOutputChunks: number;
  summaryUpdates: number;
}

export interface CursorConversationSummary {
  turns: number;
  agentTurns: number;
  shellTurns: number;
  stepCounts: Record<string, number>;
  shellCommands: number;
  shellOutputs: number;
}

export interface CursorStreamSummary {
  counts: Record<string, number>;
  statuses: string[];
  taskUpdates: number;
  requests: number;
  toolCalls: Record<string, Record<string, number>>;
  tools?: string[];
}

export interface HoneyHiveCursorInstrumentorOptions {
  apiKey?: string;
  project?: string;
  source?: string;
  serverUrl?: string;
  sanitize?: HoneyHiveSanitizer;
}

export interface TraceCursorRunOptions {
  agent: SDKAgent;
  message: CursorMessageInput;
  sessionName?: string;
  model?: string;
  cwd?: string;
  sendOptions?: Omit<SendOptions, 'onDelta' | 'onStep'>;
  onStep?: (step: ConversationStep) => void | Promise<void>;
  onDelta?: (update: InteractionUpdate) => void | Promise<void>;
  onStream?: (event: SDKMessage) => void | Promise<void>;
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
