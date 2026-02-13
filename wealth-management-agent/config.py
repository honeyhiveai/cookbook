"""
Configuration and Environment Setup for Wealth Advisory Platform

All sensitive values (API keys) must be set via environment variables.
See README.md for setup instructions.
"""

import os

# OpenAI API (required)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is required. Set it in your environment:\n"
        "  export OPENAI_API_KEY='your_openai_key_here'"
    )
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# OpenAI model (switch here to change LLM everywhere)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# SerpAPI (required for market data search tool)
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise RuntimeError(
        "SERPAPI_KEY is required for market data search. Set it in your environment:\n"
        "  export SERPAPI_KEY='your_serpapi_key_here'"
    )

# HoneyHive configuration (all from environment; init is done in main.py)
HONEYHIVE_CONFIG = {
    "api_key": os.getenv("HONEYHIVE_API_KEY"),
    "project": os.getenv("HONEYHIVE_PROJECT", "Wealth Advisory Platform"),
    "source": os.getenv("HONEYHIVE_SOURCE", "dev"),
    "session_name": os.getenv("HONEYHIVE_SESSION_NAME", "Client Advisory Trace"),
    "server_url": os.getenv("HONEYHIVE_SERVER_URL", "https://api.honeyhive.ai"),
}

if not HONEYHIVE_CONFIG["api_key"]:
    raise RuntimeError(
        "HONEYHIVE_API_KEY is required. Set it in your environment:\n"
        "  export HONEYHIVE_API_KEY='your_honeyhive_key_here'"
    )
