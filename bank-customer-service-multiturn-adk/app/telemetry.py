"""HoneyHive tracer setup. MUST be imported before anything that touches ADK.

Two things here are load-bearing and fail silently if you get them wrong:

1. GoogleADKInstrumentor().instrument() must be passed tracer_provider=...
   explicitly. HoneyHiveTracer.init() only claims the OTel *global* provider if no
   real one exists yet; if one already does, HoneyHive builds an isolated provider
   and third-party spans are dropped with no error and no warning.

2. load_dotenv() has to run before ADK reads its telemetry env vars, which is why
   it happens here and why this module is imported first.

Missing HH_API_KEY is an explicit, supported branch: we log a warning and run
untraced so the chat demo still works without credentials.
"""

import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_TRACER = None
_INITIALIZED = False


def init_telemetry():
    """Initialize HoneyHive + ADK instrumentation. Idempotent (uvicorn --reload)."""
    global _TRACER, _INITIALIZED

    if _INITIALIZED:
        return _TRACER

    load_dotenv()
    _INITIALIZED = True

    api_key = os.getenv("HH_API_KEY", "").strip()
    if not api_key:
        logger.warning(
            "HH_API_KEY is not set — running UNTRACED. "
            "The chat demo works, but nothing will reach HoneyHive and the "
            "online evaluators will have no traces to score."
        )
        return None

    from honeyhive import HoneyHiveTracer

    # No project= (deprecated in 1.5.1, removed in 2.0 — the backend infers the
    # project from the API key). No metadata= (accepted and silently dropped;
    # use tracer.enrich_session instead).
    _TRACER = HoneyHiveTracer.init(
        api_key=api_key,
        source=os.getenv("HH_SOURCE", "demo"),
        session_name="bank-cs-chat",
    )

    provider = getattr(_TRACER, "provider", None)
    if provider is None:
        # Instance attribute starts as None; every init path in 1.5.1 sets it,
        # but fall back rather than silently instrumenting nothing.
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        logger.warning(
            "tracer.provider was None; falling back to the global OTel provider."
        )

    from openinference.instrumentation.google_adk import GoogleADKInstrumentor

    GoogleADKInstrumentor().instrument(tracer_provider=provider)

    logger.info(
        "HoneyHive tracing initialized (provider=%s, is_main=%s)",
        type(provider).__name__,
        getattr(_TRACER, "is_main_provider", "?"),
    )
    return _TRACER


def get_tracer():
    """Return the tracer, initializing on first use. None when untraced."""
    if not _INITIALIZED:
        return init_telemetry()
    return _TRACER


def flush(timeout_millis: int = 30000) -> None:
    """Flush pending spans. Short-lived scripts MUST call this before exiting."""
    if _TRACER is not None:
        _TRACER.flush(timeout_millis=timeout_millis)
