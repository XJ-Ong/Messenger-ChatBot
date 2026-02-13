"""
Messenger Bot Configuration
"""
import os
from typing import List
from dotenv import load_dotenv

# Load secrets from .env
load_dotenv()

# =============================================================================
# SECRETS & API KEYS
# =============================================================================
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# =============================================================================
# GROQ API SETTINGS
# =============================================================================
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TEMPERATURE = 0.7  # 0.0 = focused, 1.0 = creative
GROQ_MAX_TOKENS = 1000  # Max response length

# Model hierarchy - fallback to next model if rate limited (429 error)
# Ordered by quality (best first)
GROQ_MODEL_HIERARCHY: List[str] = [
    "llama-3.3-70b-versatile",              # Best quality
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-120b",
    "qwen/qwen3-32b",
    "llama-3.1-8b-instant",                 # Fastest fallback
]

# System prompt - defines the bot's personality and behavior
GROQ_SYSTEM_PROMPT = """You are PrawnKing, a Messenger bot with an insanely humorous personality.

Personality:
- You LOVE making dad jokes and puns
- Friendly and genuinely helpful
- Keep responses SHORT - maximum 5 sentences

Rules:
- ALWAYS respond in the same language the user is using
- Answer any questions helpfully, but avoid sensitive topics
- NEVER make up facts - if you're unsure about something, say so honestly
- No markdown, but format your response nicely according to requests like coding
"""

# =============================================================================
# CONVERSATION MEMORY SETTINGS
# =============================================================================
MEMORY_MAX_MESSAGES = 40       # Max messages to remember per user
MEMORY_IDLE_TIMEOUT = 60       # Seconds of inactivity before memory resets
