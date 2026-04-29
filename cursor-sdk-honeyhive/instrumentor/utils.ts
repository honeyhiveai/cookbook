import path from 'node:path';

import { type HoneyHiveSanitizer, type SanitizeContext } from './types.js';

const SENSITIVE_KEY_PATTERN = /api[_-]?key|authorization|cookie|credential|password|secret|token/i;
const PATH_KEY_PATTERN = /(^|[_-])(cwd|dir|directory|file|path)$|(?:Cwd|Dir|Directory|File|Path)$/;
const REDACTED = '[redacted]';

export function compact(value: unknown, maxLength = 8000): string {
  if (value === undefined) {
    return '';
  }
  if (typeof value === 'string') {
    return value.length > maxLength ? `${value.slice(0, maxLength)}... [truncated]` : value;
  }

  const serialized = JSON.stringify(value) ?? '';
  return serialized.length > maxLength ? `${serialized.slice(0, maxLength)}... [truncated]` : serialized;
}

export function compactObject(values: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(values).filter(([, value]) => value !== undefined && value !== null && value !== ''));
}

export function defaultSanitize(value: unknown, context: SanitizeContext): unknown {
  if (context === 'workspace' && typeof value === 'string') {
    return path.basename(value);
  }
  return sanitizeValue(value);
}

export function sanitizeRecord(
  values: Record<string, unknown>,
  sanitize: HoneyHiveSanitizer,
  context: SanitizeContext,
): Record<string, unknown> {
  return compactObject(Object.fromEntries(Object.entries(values).map(([key, value]) => [key, sanitize(value, context)])));
}

export function formatError(error: unknown): string {
  if (error instanceof Error) {
    return error.stack ?? error.message;
  }
  return String(error);
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function isString(value: unknown): value is string {
  return typeof value === 'string';
}

function sanitizeValue(value: unknown, depth = 0, key?: string): unknown {
  if (typeof value === 'string') {
    if (key && PATH_KEY_PATTERN.test(key) && path.isAbsolute(value)) {
      return path.basename(value);
    }
    return truncateString(value);
  }
  if (typeof value !== 'object' || value === null) {
    return value;
  }
  if (depth >= 6) {
    return '[truncated-depth]';
  }
  if (Array.isArray(value)) {
    return value.slice(0, 50).map((item) => sanitizeValue(item, depth + 1));
  }

  return Object.fromEntries(
    Object.entries(value).slice(0, 100).map(([key, entryValue]) => [
      key,
      SENSITIVE_KEY_PATTERN.test(key) ? REDACTED : sanitizeValue(entryValue, depth + 1, key),
    ]),
  );
}

function truncateString(value: string, maxLength = 4000): string {
  return value.length > maxLength ? `${value.slice(0, maxLength)}... [truncated]` : value;
}
