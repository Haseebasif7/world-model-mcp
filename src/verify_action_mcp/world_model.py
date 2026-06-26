import os
import re
from openai import OpenAI
from dotenv import load_dotenv
from .prompts.terminal import TERMINAL_SYSTEM_PROMPT
from .prompts.swe import SWE_SYSTEM_PROMPT

load_dotenv()

# Reasoning models (e.g. qwen3.6-27b, Qwen-AgentWorld) wrap their chain of
# thought in <think>...</think>. Strip it so only the predicted observation is
# returned. Backends that support it are also asked to hide reasoning server-side.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_reasoning(text: str) -> str:
    return _THINK_BLOCK.sub("", text).strip()


# ── Backend configuration ──────────────────────────────────────────────────────

BACKEND = os.getenv("WORLD_MODEL_BACKEND", "groq").lower()

BACKEND_CONFIGS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "model": "qwen/qwen3.6-27b",
        # Groq free tier caps at 8000 TPM and counts max_tokens toward it; with
        # the large official prompt (~3k tokens), 4096 keeps the request under
        # the limit. Hidden reasoning makes 4096 enough for the final answer.
        "max_tokens": 4096,
        "hide_reasoning": True,
        "signup_url": "https://console.groq.com",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "api_key_env": "TOGETHER_API_KEY",
        "model": "Qwen/Qwen3.5-35B-A3B",  # verify against your Together dashboard
        "max_tokens": 2048,   # Together serverless output limit
        "hide_reasoning": False,
        "signup_url": "https://api.together.ai",
    },
    "qwen_agentworld": {
        "base_url": None,     # read from QWEN_AGENTWORLD_URL at runtime
        "api_key_env": None,  # no key needed for local vLLM/SGLang
        "model": "Qwen/Qwen-AgentWorld-35B-A3B",
        "max_tokens": 8192,
        "hide_reasoning": False,  # vLLM/SGLang use --reasoning-parser qwen3
        "signup_url": "https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B",
    },
}

# ── Lazy validation ─────────────────────────────────────────────────────────────
# We never raise at import time: a crash here surfaces in Claude Code only as an
# opaque "MCP server failed to connect". Instead we record any config problem and
# raise it from predict_next_state(), where server.py turns it into a readable
# message the agent can act on.

CONFIG_ERROR: str | None = None
client: OpenAI | None = None
MODEL: str | None = None
MAX_TOKENS: int = 4096
HIDE_REASONING: bool = False
base_url: str | None = None

if BACKEND not in BACKEND_CONFIGS:
    CONFIG_ERROR = (
        f"Unknown WORLD_MODEL_BACKEND: '{BACKEND}'.\n"
        f"Valid options: groq, together, qwen_agentworld."
    )
else:
    config = BACKEND_CONFIGS[BACKEND]
    MODEL = config["model"]
    MAX_TOKENS = config["max_tokens"]
    HIDE_REASONING = config["hide_reasoning"]

    if BACKEND == "qwen_agentworld":
        # The served model name varies by runtime: vLLM/SGLang use the HF id,
        # while Ollama/llama.cpp/LM Studio use their own tag. Let the user
        # override it; default to the HF id.
        MODEL = os.getenv("QWEN_AGENTWORLD_MODEL", config["model"])
        base_url = os.getenv("QWEN_AGENTWORLD_URL")
        if not base_url:
            CONFIG_ERROR = (
                "QWEN_AGENTWORLD_URL is not set.\n"
                "Point it at any OpenAI-compatible endpoint serving the model:\n"
                "  • Ollama (local):   QWEN_AGENTWORLD_URL=http://localhost:11434\n"
                "  • llama.cpp/LM Studio (local): QWEN_AGENTWORLD_URL=http://localhost:8080\n"
                "  • vLLM/SGLang (cloud GPU):     QWEN_AGENTWORLD_URL=http://YOUR_HOST:8000\n\n"
                "If the served model name differs from the HF id, also set\n"
                "QWEN_AGENTWORLD_MODEL (e.g. an Ollama tag). See the README.\n"
                "Model: https://huggingface.co/unsloth/Qwen-AgentWorld-35B-A3B-GGUF"
            )
        else:
            if not base_url.endswith("/v1"):
                base_url = base_url.rstrip("/") + "/v1"
            # Some local runtimes require a non-empty (ignored) key.
            client = OpenAI(api_key="ollama", base_url=base_url)
    else:
        base_url = config["base_url"]
        api_key = os.getenv(config["api_key_env"])
        if not api_key:
            CONFIG_ERROR = (
                f"{config['api_key_env']} is not set.\n"
                f"Get a key at: {config['signup_url']}\n"
                f"Then add it to your .env file:\n"
                f"  {config['api_key_env']}=your_key_here"
            )
        else:
            client = OpenAI(api_key=api_key, base_url=base_url)


# ── Domain routing ─────────────────────────────────────────────────────────────

DOMAIN_PROMPTS = {
    "shell_exec": TERMINAL_SYSTEM_PROMPT,
    "file_write": SWE_SYSTEM_PROMPT,
    "file_delete": SWE_SYSTEM_PROMPT,
    "git": SWE_SYSTEM_PROMPT,
    "other": TERMINAL_SYSTEM_PROMPT,
}


# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_user_message(
    action: str,
    action_type: str,
    working_directory: str,
    recent_history: str,
) -> str:
    """
    Formats the agent's action into the world-model turn format.
    Mirrors the Qwen-AgentWorld unified trajectory schema:
    (interaction history) + (current action) → predict (next observation)
    """
    lines = []

    if recent_history.strip():
        lines.append("=== Recent Interaction History ===")
        lines.append(recent_history.strip())
        lines.append("")

    lines.append("=== Current Environment State ===")
    lines.append(f"Working directory: {working_directory}")
    lines.append(f"Action type: {action_type}")
    lines.append("")
    lines.append("=== Agent Action (predict the environment response) ===")
    lines.append(action.strip())

    return "\n".join(lines)


# ── Core prediction function ───────────────────────────────────────────────────

def predict_next_state(
    action: str,
    action_type: str,
    working_directory: str,
    recent_history: str,
) -> str:
    """
    Calls the configured world model backend to predict what the environment
    will return after the agent executes the given action.

    Returns the predicted observation as a plain string.
    Raises on misconfiguration or API error — server.py catches and returns the
    message to the agent.
    """
    if CONFIG_ERROR is not None or client is None:
        raise RuntimeError(CONFIG_ERROR or "World model backend is not configured.")

    system_prompt = DOMAIN_PROMPTS.get(action_type, TERMINAL_SYSTEM_PROMPT)
    user_message = build_user_message(
        action, action_type, working_directory, recent_history
    )

    extra_body = {}
    if HIDE_REASONING:
        # Keep the reasoning model's chain of thought out of the returned content.
        extra_body["reasoning_format"] = "hidden"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=MAX_TOKENS,
        temperature=0.6,
        top_p=0.95,
        extra_body=extra_body,
    )

    return _strip_reasoning(response.choices[0].message.content or "")


def get_backend_info() -> str:
    """Returns a human-readable string describing the active backend."""
    if CONFIG_ERROR is not None:
        return f"{BACKEND} (NOT CONFIGURED)"
    if BACKEND == "qwen_agentworld":
        return f"Qwen-AgentWorld (local) @ {base_url}"
    return f"{BACKEND.title()} — {MODEL}"
