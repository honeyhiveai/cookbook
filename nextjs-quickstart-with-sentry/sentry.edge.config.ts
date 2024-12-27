// This file configures the initialization of Sentry for edge features (middleware, edge routes, and so on).
// The config you add here will be used whenever one of the edge features is loaded.
// Note that this config is unrelated to the Vercel Edge Runtime and is also required when running locally.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-node";

import * as Sentry from "@sentry/nextjs";

const client = Sentry.init({
  dsn: "https://9ee4c459dfa78219cbbf58400823e876@o4505324721340416.ingest.us.sentry.io/4507510929031168",

  // Define how likely traces are sampled. Adjust this value in production, or use tracesSampler for greater control.
  tracesSampleRate: 1,

  // Setting this option to true will print useful information to the console while you're setting up Sentry.
  debug: false,
} as Sentry.NodeOptions) as Sentry.NodeClient;

client?.traceProvider?.addSpanProcessor(
  new BatchSpanProcessor(new OTLPTraceExporter(
    {
      url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT,
      headers: {
        "Authorization": `Bearer ${process.env.HH_API_KEY}`,
        "x-honeyhive": `project:${process.env.HH_PROJECT_NAME}`,
      },
    }
  )),
);
