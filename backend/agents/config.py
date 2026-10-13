"""Portkey / model configuration for the Campus Customs team.

Loads .env from the project folder and every folder above it (nearest wins), so
the class-wide .env holding PORTKEY_API_KEY works without copying the key around.

gpt-6-luna needs the Responses API for function tools — chat/completions rejects
tools on this model. Every agent on the team uses this one model; there is no
second model anywhere in this project.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
for folder in [PROJECT_ROOT, *PROJECT_ROOT.parents]:
    if (folder / ".env").exists():
        load_dotenv(folder / ".env", override=False)

# The only model this project uses.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")

MCP_CONFIG_PATH = PROJECT_ROOT / ".mcp.json"
PROMPTS_DIR = PROJECT_ROOT / "backend" / "prompts"
AUDIT_PATH = PROJECT_ROOT / "output" / "audit_trail.json"

# --- Budget limits, enforced in code (CC-OPS-25..30) ---
MAX_DELEGATIONS = 10        # CC-OPS-25, per ticket, across all agents
MAX_DEPTH = 3               # CC-OPS-26
MAX_TOOL_CALLS_PER_AGENT = 8  # CC-OPS-28
MAX_TRACE_CHARS = 600       # CC-OPS-30
MAX_REQUESTS_PER_AGENT = 10   # CC-OPS-33, model round-trips in one agent loop
AGENT_TIMEOUT_S = 120.0       # CC-OPS-34, wall clock for one agent loop
TICKET_TIMEOUT_S = 600.0      # CC-OPS-34, wall clock for a whole ticket
HTTP_TIMEOUT_S = 45.0         # CC-OPS-34, per model request
HTTP_MAX_RETRIES = 1          # CC-OPS-34, see build_model()

# Tools the agents must never see. approve_pending is the only tool that moves
# money, and it belongs to the human at the dashboard (CC-OPS-1).
HUMAN_ONLY_TOOLS = frozenset({"approve_pending"})


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is missing. Put it in a .env in this project or a parent folder."
        )
    return key


@lru_cache(maxsize=2)
def build_model(model_name: str | None = None) -> OpenAIResponsesModel:
    """One model for every agent, routed through Portkey."""
    # Measured on this endpoint, latency is bimodal: a healthy call returns in
    # 5-15s, a wedged one never returns. The old 90s x 3 retries turned one bad
    # call into 270s and ate a specialist's entire 300s budget before it could
    # answer. Retrying a wedged call is near-worthless, so fail fast and retry
    # once: worst case 90s instead of 270s (CC-OPS-34).
    client = AsyncOpenAI(
        api_key=require_api_key(),
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
        timeout=HTTP_TIMEOUT_S,
        max_retries=HTTP_MAX_RETRIES,
    )
    return OpenAIResponsesModel(
        model_name or MODEL_NAME, provider=OpenAIProvider(openai_client=client)
    )
