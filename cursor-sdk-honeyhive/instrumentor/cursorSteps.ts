import {
  type ToolConversationStep,
} from './types.js';
import { isRecord } from './utils.js';

export function getToolArgs(tool: ToolConversationStep['message']): unknown {
  return 'args' in tool ? tool.args : undefined;
}

export function getToolResult(tool: ToolConversationStep['message']): unknown {
  return 'result' in tool ? tool.result : undefined;
}

export function getToolResultStatus(tool: ToolConversationStep['message']): string {
  const result = getToolResult(tool);
  if (isRecord(result) && typeof result.status === 'string') {
    return result.status;
  }
  return result === undefined ? 'unknown' : 'completed';
}

export function getToolExecutionTimeMs(tool: ToolConversationStep['message']): number | undefined {
  const result = getToolResult(tool);
  if (!isRecord(result) || !isRecord(result.value)) {
    return undefined;
  }
  return typeof result.value.executionTime === 'number' ? result.value.executionTime : undefined;
}
