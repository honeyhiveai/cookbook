import { type Context, trace } from '@opentelemetry/api'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'
import {
  BatchSpanProcessor,
  type ReadableSpan,
  type Span,
  type SpanProcessor,
} from '@opentelemetry/sdk-trace-base'
import { NodeTracerProvider } from '@opentelemetry/sdk-trace-node'

// Strands sets traceAttributes only on the root agent span.
// HoneyHive groups spans by honeyhive.session_id, so copy it to every child span.
class HoneyHiveSessionPropagator implements SpanProcessor {
  onStart(span: Span, parentContext: Context): void {
    const parent = trace.getSpan(parentContext) as ReadableSpan | undefined
    for (const [key, value] of Object.entries(parent?.attributes ?? {})) {
      if (key.startsWith('honeyhive.') && value !== undefined) {
        span.setAttribute(key, value)
      }
    }
  }
  onEnd(): void {}
  async forceFlush(): Promise<void> {}
  async shutdown(): Promise<void> {}
}

/**
 * Registers a global tracer provider that exports Strands spans to HoneyHive over OTLP/HTTP.
 * Import this module before the Strands SDK so the agent picks up this provider.
 */
export function setupTracing(apiKey: string, dataPlaneUrl: string): NodeTracerProvider {
  const provider = new NodeTracerProvider({
    spanProcessors: [
      new HoneyHiveSessionPropagator(),
      new BatchSpanProcessor(
        new OTLPTraceExporter({
          url: `${dataPlaneUrl}/opentelemetry/v1/traces`,
          headers: { Authorization: `Bearer ${apiKey}` },
        }),
      ),
    ],
  })
  provider.register()
  return provider
}
