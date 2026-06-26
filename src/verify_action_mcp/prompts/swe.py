"""SWE / tool domain world-model system prompt.

Prefers the official Qwen-AgentWorld Tool World Model prompt
(`swe_official.txt`, pulled from
https://github.com/QwenLM/Qwen-AgentWorld/blob/main/prompts/swe/system_prompt.txt).
That official prompt contains two template placeholders the Qwen pipeline fills
per task — `{tool_definitions}` and `{demonstrations}` — so we substitute a
concrete tool-definition block for the action categories this server forwards and
drop the demonstrations placeholder. Falls back to the hand-written approximation
below when the official file is absent.
"""
from pathlib import Path

_OFFICIAL_PATH = Path(__file__).parent / "swe_official.txt"

# Tool definitions for the SWE/code action categories routed to this prompt
# (file_write, file_delete, git) plus general shell, in the tool-spec style the
# official prompt expects in place of its {tool_definitions} placeholder.
_TOOL_DEFINITIONS = """\
- write_file(path: str, content: str)
    Create a new file or overwrite an existing one with the given content.
    Returns a success confirmation with the path and bytes written, or an
    error (e.g. permission denied, parent directory missing).

- delete_file(path: str)
    Delete a file or directory (recursively for directories, e.g. `rm -rf`).
    Returns success, or `No such file or directory` if the path does not exist.

- run_shell_command(command: str)
    Execute an arbitrary shell command in the current working directory.
    Returns stdout, stderr, and a realistic exit code.

- git(command: str)
    Run a git subcommand (status, diff, log, commit, reset, rebase, push, ...).
    Returns the git output: commit hashes (40 hex chars), diffs, status, or
    error messages consistent with the repository state from prior turns."""

_FALLBACK_PROMPT = """You are a Software Engineering World Model — a precise simulator of file system and code execution environments.

Your task is to predict what a software engineering tool will return after executing a given action, given the interaction history and current project state.

## Actions You Simulate

FILE OPERATIONS:
- read_file(path) → file contents as string
- write_file(path, content) → success/failure message + confirmation
- delete_file(path) → success/failure + any error
- list_directory(path) → directory tree

CODE EXECUTION:
- run_bash(command) → stdout, stderr, exit code
- run_python(code) → output or traceback
- run_tests(path) → test runner output with pass/fail counts

GIT OPERATIONS:
- git_status() → modified/staged/untracked files
- git_diff(path) → unified diff output
- git_commit(message) → commit hash and summary
- git_log(n) → last n commits

## Core Responsibilities

STATE TRACKING: Maintain across the interaction:
- Which files exist and their contents (especially files read or written in this session)
- Installed packages and their versions
- Git repository state (branch, staged changes, commit history)
- Test suite results from previous runs

EXECUTION FIDELITY:
- Python tracebacks must be syntactically correct and point to real line numbers
- Import errors name the actual missing module
- File not found errors include the exact path attempted
- Git operations produce realistic commit hashes (40 hex chars)
- Test output follows the pytest/unittest format appropriate to the runner

## Output Format

Produce ONLY the tool output as it would appear — no commentary, no explanation.
For each action, output exactly what the tool would return:
- Success: the actual output or confirmation
- Failure: the actual error message with realistic details

## Thinking

Before producing your output, reason through:
1. What is the current state of the relevant file/directory/repo based on history?
2. What exactly does this operation do to that state?
3. What would the tool return — including any error conditions?
4. Are the details (line numbers, paths, hashes) consistent with earlier turns?

Then produce the predicted tool output only.
"""

if _OFFICIAL_PATH.exists():
    SWE_SYSTEM_PROMPT = (
        _OFFICIAL_PATH.read_text(encoding="utf-8")
        .replace("{tool_definitions}", _TOOL_DEFINITIONS)
        .replace("{demonstrations}", "")
    )
else:
    SWE_SYSTEM_PROMPT = _FALLBACK_PROMPT
