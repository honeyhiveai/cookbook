"""
Configuration and Environment Setup for Wealth Advisory Platform

All sensitive values (API keys) must be set via environment variables.
See README.md for setup instructions.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

# OpenAI API (required)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY is required. Set it in your .env file or environment."
    )
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# OpenAI model (switch here to change LLM everywhere)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# SerpAPI (required for market data search tool)
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    raise RuntimeError(
        "SERPAPI_KEY is required for market data search. Set it in your .env file or environment."
    )

# HoneyHive configuration (all from environment; init is done in main.py)
HONEYHIVE_CONFIG = {
    "api_key": os.getenv("HH_API_KEY"),
    "project": os.getenv("HH_PROJECT", "Wealth Advisory Platform"),
    "source": os.getenv("HH_SOURCE", "dev"),
    "session_name": os.getenv("HH_SESSION_NAME", "Client Advisory Trace"),
}

if not HONEYHIVE_CONFIG["api_key"]:
    raise RuntimeError(
        "HH_API_KEY is required. Set it in your .env file or environment."
    )
