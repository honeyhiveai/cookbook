import { type Context, trace } from '@opentelemetry/api'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'
import {
  BatchSpanProcessor,
  type ReadableSpan,
  type Span,
  type SpanProcessor,
} from '@opentelemetry/sdk-trace-base'
import { NodeTracerProvider } from '@opentelemetry/sdk-trace-node'

// Strands TS sets traceAttributes only on the agent span. Copy honeyhive.session_id to child spans.
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

/** Exports Strands spans to HoneyHive over OTLP. Call it before the first agent runs. */
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
