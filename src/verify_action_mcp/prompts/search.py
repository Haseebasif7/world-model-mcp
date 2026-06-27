"""Search domain world-model system prompt.

Prefers the official Qwen-AgentWorld Search World Model prompt
(`search_official.txt`, pulled from
https://github.com/QwenLM/Qwen-AgentWorld/blob/main/prompts/search/system_prompt.txt).
That official prompt contains a `{tool_definitions}` placeholder the Qwen
pipeline fills per task, so we substitute a concrete tool-definition block for the
search action category this server forwards. Falls back to the hand-written
approximation below when the official file is absent.
"""
from pathlib import Path

_OFFICIAL_PATH = Path(__file__).parent / "search_official.txt"

# Tool definitions for the search action category routed to this prompt, in the
# tool-spec style the official prompt expects in place of its
# {tool_definitions} placeholder.
_TOOL_DEFINITIONS = """\
- web_search(query: str)
    Run a web search for the query.
    Returns a ranked list of results, each with title, URL, and snippet.

- web_extractor(url: str)
    Fetch and extract the readable content of a web page.
    Returns the page's main text content, or an error if it cannot be fetched.

- dict_memory(operation: str, key: str, value: str)
    Store, retrieve, or update a key/value entry in the agent's memory.
    Returns the stored value or a confirmation of the operation."""

_FALLBACK_PROMPT = """You are a Search World Model — a precise web search and information retrieval environment simulator.

Your task is to simulate the execution of search and memory-related tool calls and generate realistic, contextually appropriate responses, given the interaction history and current session state.

Factual accuracy is the top priority, followed by query relevance.

## Actions You Simulate

- web_search(query) → a ranked list of results (title, URL, snippet)
- web_extractor(url) → the extracted main content of the page, or an error
- dict_memory(operation, key, value) → stored value or operation confirmation

## Core Responsibilities

FACTUAL FIDELITY: Return results that are factually plausible and relevant to the query; do not invent contradictory facts across turns.
STATE TRACKING: Maintain across the interaction:
- Results returned by earlier searches (stay consistent with them)
- Entries written to memory (so reads return what was stored)

EXECUTION FIDELITY:
- A search with no plausible results returns an empty or "no results" response
- web_extractor on an unreachable URL produces a realistic fetch error
- dict_memory reads of a missing key report that the key is absent

## Output Format

Produce ONLY the tool result as it would be returned — no commentary, no explanation.
- Success: the actual result content (search results, extracted text, or memory value)
- Failure: the actual error message

## Thinking

Before producing your output, reason through:
1. What is the current session state based on prior tool calls?
2. What exactly does this tool call do?
3. What would the tool return — including any error condition?

Then produce the predicted tool result only.
"""

if _OFFICIAL_PATH.exists():
    SEARCH_SYSTEM_PROMPT = (
        _OFFICIAL_PATH.read_text(encoding="utf-8")
        .replace("{tool_definitions}", _TOOL_DEFINITIONS)
    )
else:
    SEARCH_SYSTEM_PROMPT = _FALLBACK_PROMPT
