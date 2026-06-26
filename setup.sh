#!/bin/bash
set -e

echo "=== verify-action-mcp setup ==="
echo ""

# ── Python version check ────────────────────────────────────────────────────
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required="3.11"
if [[ "$(printf '%s\n' "$required" "$python_version" | sort -V | head -n1)" != "$required" ]]; then
    echo "ERROR: Python 3.11+ required. You have $python_version"
    exit 1
fi

# ── Ensure uv is installed ──────────────────────────────────────────────────
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Modern uv installs to ~/.local/bin
    export PATH="$HOME/.local/bin:$PATH"
fi

# ── Create the virtual environment and install ──────────────────────────────
echo "Creating virtual environment and installing dependencies..."
uv venv
uv pip install -e .

# ── Create .env from the example if missing ─────────────────────────────────
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "Created .env from .env.example"
    echo "  --> Open .env and add your API key:"
    echo "      GROQ_API_KEY=gsk_...   (free at https://console.groq.com)"
    echo ""
else
    echo ".env already exists — skipping"
fi

# ── Pull official Qwen-AgentWorld prompts (optional; fallback prompts exist) ──
echo "Pulling official Qwen-AgentWorld system prompts..."
if command -v git &> /dev/null; then
    rm -rf /tmp/qwen-agentworld-prompts
    if git clone --quiet --depth=1 \
        https://github.com/QwenLM/Qwen-AgentWorld.git \
        /tmp/qwen-agentworld-prompts 2>/dev/null \
        && [ -d "/tmp/qwen-agentworld-prompts/prompts" ]; then
        cp /tmp/qwen-agentworld-prompts/prompts/terminal/system_prompt.txt \
           src/verify_action_mcp/prompts/terminal_official.txt
        cp /tmp/qwen-agentworld-prompts/prompts/swe/system_prompt.txt \
           src/verify_action_mcp/prompts/swe_official.txt
        rm -rf /tmp/qwen-agentworld-prompts
        echo "Official prompts installed."
    else
        echo "Could not pull official prompts — using built-in fallback prompts."
        echo "(Fine for Groq and Together AI backends.)"
    fi
fi

# ── Resolve the installed entry point and print Claude Code config ──────────
bin_path="$(uv run which verify-action-mcp 2>/dev/null || true)"
[ -z "$bin_path" ] && bin_path="$(pwd)/.venv/bin/verify-action-mcp"

echo ""
echo "=== Connect your agent (Claude Code, Cursor, Windsurf, VS Code, ...) ==="
echo ""
echo "This is a standard stdio MCP server. Add it to your harness with this config"
echo "(Cursor: ~/.cursor/mcp.json | Windsurf: ~/.codeium/windsurf/mcp_config.json |"
echo " Claude Code: .mcp.json | VS Code: .vscode/mcp.json — uses key 'servers'):"
cat << EOF
{
  "mcpServers": {
    "verify-action": {
      "command": "$bin_path",
      "args": [],
      "env": {
        "WORLD_MODEL_BACKEND": "groq",
        "GROQ_API_KEY": "gsk_your_key_here"
      }
    }
  }
}
EOF
echo ""
echo "Claude Code shortcut (CLI):"
echo "  claude mcp add verify-action \\"
echo "    --env WORLD_MODEL_BACKEND=groq \\"
echo "    --env GROQ_API_KEY=gsk_your_key_here \\"
echo "    -- \"$bin_path\""
echo ""
echo "=== Setup complete ==="
echo "Restart / re-open your agent after wiring the config."
