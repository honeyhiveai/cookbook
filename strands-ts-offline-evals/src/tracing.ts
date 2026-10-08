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
// HoneyHive needs honeyhive.session_id on every span, so copy it to child spans.
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

const dataPlaneUrl = (process.env.HH_DATA_PLANE_URL || 'https://api.dp1.us.honeyhive.ai').replace(/\/+$/, '')

export const provider = new NodeTracerProvider({
  spanProcessors: [
    new HoneyHiveSessionPropagator(),
    new BatchSpanProcessor(
      new OTLPTraceExporter({
        url: `${dataPlaneUrl}/opentelemetry/v1/traces`,
        headers: { Authorization: `Bearer ${process.env.HH_PROJECT_API_KEY}` },
      }),
    ),
  ],
})
provider.register()
