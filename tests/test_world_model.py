"""
Test the configured world model backend end to end (no MCP needed).

Usage:
    WORLD_MODEL_BACKEND=groq            uv run python tests/test_world_model.py
    WORLD_MODEL_BACKEND=together        uv run python tests/test_world_model.py
    WORLD_MODEL_BACKEND=qwen_agentworld uv run python tests/test_world_model.py
"""
from verify_action_mcp.world_model import predict_next_state, get_backend_info

print(f"=== Testing backend: {get_backend_info()} ===\n")

TESTS = [
    {
        "name": "Safe read-only (baseline — should produce normal ls output)",
        "action": "ls -la ./src/",
        "action_type": "shell_exec",
        "working_directory": "/home/user/project",
        "recent_history": "",
    },
    {
        "name": "Irreversible delete (should show files being removed)",
        "action": "rm -rf ./dist/",
        "action_type": "file_delete",
        "working_directory": "/home/user/project",
        "recent_history": (
            "Action: ls ./\n"
            "Result: dist/  src/  tests/  README.md  pyproject.toml\n\n"
            "Action: ls ./dist/\n"
            "Result: main.js  main.css  index.html  assets/\n"
        ),
    },
    {
        "name": "Git reset hard (should show commit hash and lost work)",
        "action": "git reset --hard HEAD~3",
        "action_type": "git",
        "working_directory": "/home/user/project",
        "recent_history": (
            "Action: git log --oneline -5\n"
            "Result:\n"
            "a1b2c3d feat: add payment integration\n"
            "e4f5g6h fix: correct tax calculation\n"
            "i7j8k9l refactor: split checkout module\n"
            "m0n1o2p feat: add cart persistence\n"
            "q3r4s5t initial commit\n"
        ),
    },
    {
        "name": "Force push (should confirm history rewrite)",
        "action": "git push --force origin main",
        "action_type": "git",
        "working_directory": "/home/user/project",
        "recent_history": (
            "Action: git log --oneline -3\n"
            "Result:\n"
            "a1b2c3d feat: add payment integration\n"
            "e4f5g6h fix: correct tax calculation\n"
            "i7j8k9l initial commit\n"
        ),
    },
]

for test in TESTS:
    print(f"--- {test['name']} ---")
    result = predict_next_state(
        action=test["action"],
        action_type=test["action_type"],
        working_directory=test["working_directory"],
        recent_history=test["recent_history"],
    )
    print(result)
    print()

print("=== All tests complete ===")
