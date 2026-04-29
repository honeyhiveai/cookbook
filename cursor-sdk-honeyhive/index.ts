import 'dotenv/config';

import { Agent } from '@cursor/sdk';

import { HoneyHiveCursorInstrumentor } from './instrumentor/index.js';

const cursorApiKey = readRequiredEnv('CURSOR_API_KEY');
const honeyHiveApiKey = readRequiredEnv('HH_API_KEY');
const model = process.env.CURSOR_MODEL || 'composer-2';
const workspaceDir = process.env.CURSOR_WORKSPACE_DIR || process.cwd();

const instrumentor = new HoneyHiveCursorInstrumentor({
  apiKey: honeyHiveApiKey,
  project: process.env.HH_PROJECT || 'Cursor SDK HoneyHive Demo',
  source: process.env.HH_SOURCE || 'cursor-sdk-honeyhive',
});

const agent = await Agent.create({
  apiKey: cursorApiKey,
  model: { id: model },
  local: { cwd: workspaceDir },
});

try {
  const result = await instrumentor.traceRun({
    agent,
    message:
      process.env.CURSOR_PROMPT ||
      'Read README.md in this repository, then summarize what this Cursor SDK HoneyHive example does in one sentence. Do not modify files.',
    sessionName: 'Cursor SDK HoneyHive Demo',
    model,
    cwd: workspaceDir,
  });

  console.log('Exported Cursor SDK trace to HoneyHive:');
  console.log(JSON.stringify(result, null, 2));
} finally {
  await agent[Symbol.asyncDispose]();
}

function readRequiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}
