import { type ClientConfig } from '@honeyhive/api-client';

import { type HoneyHiveCursorInstrumentorOptions } from './types.js';

export function createClientConfig(options: HoneyHiveCursorInstrumentorOptions): ClientConfig {
  return {
    projectApiKey: options.apiKey,
    dataPlaneUrl: options.serverUrl ?? process.env.HH_API_URL,
  };
}
