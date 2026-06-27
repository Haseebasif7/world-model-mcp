import asyncio
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from .world_model import predict_next_state, get_backend_info

# ── MCP server setup ───────────────────────────────────────────────────────────
app = Server("verify-action-mcp")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="verify_action",
            description=(
                "Before executing an action that could have significant, hard-to-reverse, "
                "or unexpected consequences, call this tool to predict what the environment "
                "will return after the action executes. Use this when you are uncertain about "
                "side effects, when an action permanently modifies state, or when a wrong "
                "action would be costly to recover from.\n\n"
                "DO NOT call this for every action — only for consequential ones such as:\n"
                "- Deleting or overwriting files\n"
                "- Running shell commands with side effects (rm, mv, chmod, kill, etc.)\n"
                "- Git operations that modify history (reset, rebase, force push)\n"
                "- Writing to config files or environment variables\n"
                "- Installing or uninstalling packages\n\n"
                "Returns a predicted environment response. Read it carefully before deciding "
                "whether to proceed, modify your action, or pause and ask the user."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": (
                            "The exact command, tool call, or action you are about to take. "
                            "Be precise — the prediction quality depends on this."
                        ),
                    },
                    "action_type": {
                        "type": "string",
                        "enum": [
                            "shell_exec",
                            "file_write",
                            "file_delete",
                            "git",
                            "web",
                            "mcp",
                            "search",
                            "android",
                            "os",
                            "other",
                        ],
                        "description": "Category of the action.",
                    },
                    "working_directory": {
                        "type": "string",
                        "description": (
                            "The current working directory. Important for relative path resolution."
                        ),
                    },
                    "recent_history": {
                        "type": "string",
                        "description": (
                            "The last 3-5 actions you took and their results, in plain text. "
                            "This gives the world model context about the current environment state. "
                            "Format as: 'Action: <cmd>\\nResult: <output>\\n' per turn. "
                            "Can be empty string if this is the first action."
                        ),
                    },
                },
                "required": ["action", "action_type", "working_directory", "recent_history"],
            },
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "verify_action":
        raise ValueError(f"Unknown tool: {name}")

    try:
        prediction = predict_next_state(
            action=arguments["action"],
            action_type=arguments["action_type"],
            working_directory=arguments["working_directory"],
            recent_history=arguments.get("recent_history", ""),
        )

        result = (
            "=== WORLD MODEL PREDICTION ===\n"
            "This is a simulation of what the environment will likely return "
            "after you execute the action. It is not guaranteed to be exact.\n\n"
            f"{prediction}\n\n"
            "=== END PREDICTION ===\n"
            "Decide whether to proceed based on this predicted outcome."
        )

    except Exception as e:
        result = (
            f"=== WORLD MODEL ERROR ===\n"
            f"Could not generate prediction: {str(e)}\n"
            "Proceed with caution and your own judgment."
        )

    return [types.TextContent(type="text", text=result)]


# ── Entry point ────────────────────────────────────────────────────────────────
async def main():
    # Log to stderr (stdout is the MCP transport) so users can see which
    # world model backend is active when the server starts.
    print(f"[verify-action-mcp] backend: {get_backend_info()}", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
