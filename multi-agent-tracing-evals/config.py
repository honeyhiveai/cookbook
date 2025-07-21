"""
Configuration and Environment Setup
"""

import os
from honeyhive.tracer import HoneyHiveTracer

# OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    OPENAI_API_KEY = input("Enter your OpenAI API key: ").strip()
    if not OPENAI_API_KEY:
        raise RuntimeError("An OpenAI API key is required to run this demo.")
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# SerpAPI
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
if not SERPAPI_KEY:
    SERPAPI_KEY = input("Enter your SerpAPI key: ").strip()
    if not SERPAPI_KEY:
        raise RuntimeError("A SerpAPI key is required for web search functionality.")

# HoneyHive configuration (init moved to main function)
HONEYHIVE_CONFIG = {
    'api_key': os.getenv("HONEYHIVE_API_KEY"),
    'project': os.getenv("HONEYHIVE_PROJECT", "Multi Agent"),
    'source': os.getenv("HONEYHIVE_SOURCE", "dev"),
    'session_name': os.getenv("HONEYHIVE_SESSION_NAME", "Multi-Agent Trace"),
    'server_url': os.getenv("HONEYHIVE_SERVER_URL", "https://api.honeyhive.ai")
}