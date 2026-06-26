# verify-action-mcp

A tiny [MCP](https://modelcontextprotocol.io) server that gives a coding agent a
**world model to consult before consequential actions**. It exposes one tool —
`verify_action` — that an agent calls *before* doing something hard to reverse
(deleting files, destructive shell commands, history-rewriting git ops). The
server asks a world-model LLM to predict the environment's response, and returns
that prediction so the agent can decide whether to proceed, change course, or ask
the user.

> It is an **oracle the agent consults voluntarily**, not a guardrail that blocks
> actions. The agent's own reasoning decides what to do with the prediction.

## How it works

```
Agent (Claude Code) ──verify_action──▶ verify-action-mcp ──▶ world-model LLM
        ▲                                                          │
        └──────────────  predicted environment response  ◀────────┘
```

The action is routed to a domain system prompt (terminal vs. software-engineering),
combined with recent interaction history, and sent to the configured backend.

## Backends

One environment variable (`WORLD_MODEL_BACKEND`) selects the backend:

| Backend | Model | Cost | Setup |
|---|---|---|---|
| `groq` (default) | `qwen/qwen3.6-27b` | Free, no card | Hosted | ~2 min |
| `together` | `Qwen/Qwen3.5-35B-A3B`¹ | $25 free credit | Hosted | ~2 min |
| `qwen_agentworld` | `Qwen-AgentWorld-35B-A3B` | Your hardware | **Local or cloud** | ~10–20 min |

¹ Confirm the exact Together model id against your dashboard — serverless catalogs
change and a wrong id returns *model not found*.

**You do not need a GPU to start.** Use Groq (free, hosted) for setup in 2 minutes.
The `qwen_agentworld` backend — the real, purpose-built world model — can run either
**locally** (quantized GGUF via Ollama/llama.cpp) or in the **cloud** (full precision
via vLLM/SGLang on a rented GPU). See [Running the real model](#running-the-real-model-local-or-cloud).

## Quick start

```bash
git clone https://github.com/Haseebasif7/world-model-mcp.git
cd world-model-mcp
./setup.sh          # creates venv, installs, pulls official prompts, prints config
```

Then put your key in `.env` (created from `.env.example`):

```env
WORLD_MODEL_BACKEND=groq
GROQ_API_KEY=gsk_your_key_here   # free at https://console.groq.com
```

### Manual install (without setup.sh)

```bash
uv venv
uv pip install -e .
cp .env.example .env   # then edit .env
```

## Connect your agent

This is a standard **stdio MCP server**, so it works with any MCP-compatible
harness — Claude Code, Cursor, Windsurf, VS Code (Copilot), Claude Desktop, and
others. They all use the same idea: register a server with a `command`, `args`,
and `env`. Use the absolute path to the installed binary:

```
<repo>/.venv/bin/verify-action-mcp
```

The shared config shape (Cursor, Windsurf, Claude Desktop, Claude Code `.mcp.json`):

```json
{
  "mcpServers": {
    "verify-action": {
      "command": "/abs/path/to/.venv/bin/verify-action-mcp",
      "args": [],
      "env": {
        "WORLD_MODEL_BACKEND": "groq",
        "GROQ_API_KEY": "gsk_your_key_here"
      }
    }
  }
}
```

Where each harness reads it:

| Harness | Config location |
|---|---|
| **Claude Code** | `claude mcp add` (below), or project `.mcp.json`, or `~/.claude.json` |
| **Cursor** | `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project) |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` |
| **Claude Desktop** | `claude_desktop_config.json` |
| **VS Code (Copilot)** | `.vscode/mcp.json` — note: top-level key is `servers`, not `mcpServers` |

**Claude Code shortcut (CLI):**

```bash
claude mcp add verify-action \
  --env WORLD_MODEL_BACKEND=groq \
  --env GROQ_API_KEY=gsk_your_key_here \
  -- "$(pwd)/.venv/bin/verify-action-mcp"
```

Copy `.mcp.json.example` to get started, then restart / re-open the project in your
harness. On startup the server logs the active backend to stderr, e.g.
`[verify-action-mcp] backend: Groq — qwen/qwen3.6-27b`.

## Security

- **Never commit real keys.** `.env` and `.mcp.json` are gitignored; the repo ships
  only `.env.example` and `.mcp.json.example` with placeholders.
- If a key is ever exposed, **rotate it** at the provider.

## Testing

```bash
WORLD_MODEL_BACKEND=groq uv run python tests/test_world_model.py
```

Runs four scenarios (read-only `ls`, `rm -rf`, `git reset --hard`, `git push --force`)
and prints the world model's predicted output for each.

## Running the real model (local or cloud)

The `qwen_agentworld` backend talks to **any OpenAI-compatible endpoint** serving the
model, so you choose the path that matches your hardware. In both cases you only set
two env vars — `QWEN_AGENTWORLD_URL` (where it's served) and `QWEN_AGENTWORLD_MODEL`
(the served name) — no code changes.

All local options use a **quantized GGUF**. Pick a quant that fits your VRAM/RAM
(lower bits = smaller + faster, but lower fidelity):

| Quant | Size | Fits on |
|---|---|---|
| `Q2_K_XL` (2-bit) | ~12 GB | 16 GB GPU, or a 16 GB+ Mac, or CPU+RAM |
| `Q4_K_M` (4-bit, recommended) | ~22 GB | 24 GB GPU (4090/3090), 32 GB+ Mac |
| `BF16` (full) | ~69 GB | the cloud/multi-GPU path below |

### Option 1a — Local with Ollama (simplest)

```bash
# Ollama exposes an OpenAI-compatible API on :11434
ollama run hf.co/unsloth/Qwen-AgentWorld-35B-A3B-GGUF:Q4_K_M
```

```env
WORLD_MODEL_BACKEND=qwen_agentworld
QWEN_AGENTWORLD_URL=http://localhost:11434
QWEN_AGENTWORLD_MODEL=hf.co/unsloth/Qwen-AgentWorld-35B-A3B-GGUF:Q4_K_M
```

### Option 1b — Local with llama.cpp

[`llama-server`](https://github.com/ggml-org/llama.cpp) downloads the GGUF straight
from Hugging Face and serves an OpenAI-compatible API. Install via
`brew install llama.cpp` (macOS) or build from source, then:

```bash
# -hf pulls the quant from HF; --port sets the OpenAI-compatible endpoint
llama-server -hf unsloth/Qwen-AgentWorld-35B-A3B-GGUF:Q4_K_M \
    --port 8080 --ctx-size 16384 --jinja
```

```env
WORLD_MODEL_BACKEND=qwen_agentworld
QWEN_AGENTWORLD_URL=http://localhost:8080
# llama-server ignores the request's model field, so any non-empty value works:
QWEN_AGENTWORLD_MODEL=qwen-agentworld
```

> `--ctx-size` controls context length (raise it if you have memory; the full model
> supports up to 262,144). `--jinja` enables the model's chat template. LM Studio also
> works the same way — start its local server and point `QWEN_AGENTWORLD_URL` at it.

### Option 2 — Cloud, full precision on a rented GPU (best quality)

For the unquantized model, rent a multi-GPU host (~70 GB+ VRAM; e.g. 2× A100 80GB on
[RunPod](https://www.runpod.io)/[Lambda](https://lambdalabs.com)) and serve with vLLM
or SGLang:

```bash
# vLLM — --language-model-only is required: the checkpoint ships only LM weights
vllm serve Qwen/Qwen-AgentWorld-35B-A3B \
    --port 8000 --tensor-parallel-size 4 \
    --max-model-len 262144 --reasoning-parser qwen3 \
    --language-model-only --trust-remote-code
```

```env
WORLD_MODEL_BACKEND=qwen_agentworld
QWEN_AGENTWORLD_URL=http://YOUR_HOST:8000
QWEN_AGENTWORLD_MODEL=Qwen/Qwen-AgentWorld-35B-A3B
```

The model's default context length is **262,144** tokens (lower it for less VRAM).
Recommended sampling: `temperature=0.6, top_p=0.95, top_k=20`.

## Links

- Qwen-AgentWorld (full): https://huggingface.co/Qwen/Qwen-AgentWorld-35B-A3B
- Qwen-AgentWorld (GGUF, for local): https://huggingface.co/unsloth/Qwen-AgentWorld-35B-A3B-GGUF
- Qwen-AgentWorld repo (prompts/eval): https://github.com/QwenLM/Qwen-AgentWorld
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk

## License

MIT — see [LICENSE](LICENSE).
