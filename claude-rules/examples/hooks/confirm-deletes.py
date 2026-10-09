#!/usr/bin/env python3
"""PreToolUse hook: make Claude ask before any shell command that deletes files.

Deletes inside Claude's own scratch folder are allowed without asking.
Prints a permission "ask" decision on stdout; prints nothing to let the command run.
"""
import json
import os
import re
import shlex
import sys

DELETE_TOOLS = {"rm", "rmdir", "unlink", "shred"}
# Commands that run another command: `sudo rm`, `xargs rm`, `find -exec rm`.
WRAPPERS = {"sudo", "xargs", "exec", "nohup", "time", "command", "env", "nice"}
EXEC_FLAGS = {"-exec", "-execdir", "-ok", "-okdir"}
SCRATCH = f"/tmp/claude-{os.getuid()}/"


def segments(command):
    parts = re.split(r"\|\||&&|[;|&\n]|\$\(|`|\(|\)", command)
    for part in parts:
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            tokens = part.split()
        if tokens:
            yield tokens


def command_starts(tokens):
    """Yield indexes where a command name sits."""
    i = 0
    while i < len(tokens) and ("=" in tokens[i] or tokens[i] in WRAPPERS
                               or (i and tokens[i].startswith("-"))):
        i += 1
    yield i
    for j, tok in enumerate(tokens):
        if tok in EXEC_FLAGS:
            yield j + 1


def in_scratch(paths):
    return paths and all(os.path.abspath(os.path.expanduser(p)).startswith(SCRATCH)
                         for p in paths)


def check(tokens):
    for i in command_starts(tokens):
        if i >= len(tokens):
            continue
        tool = tokens[i].rsplit("/", 1)[-1]
        rest = tokens[i + 1:]
        if tool in DELETE_TOOLS:
            paths = [t for t in rest if not t.startswith("-")]
            if not in_scratch(paths):
                return f"`{tool}` deletes files"
        if tool == "find" and "-delete" in rest:
            return "`find -delete` deletes files"
        if tool == "git" and rest:
            sub = next((t for t in rest if not t.startswith("-")), "")
            if sub in {"clean", "rm"}:
                return f"`git {sub}` deletes files"
            if sub == "reset" and "--hard" in rest:
                return "`git reset --hard` discards changes"
            if sub == "restore" or (sub == "checkout" and "--" in rest):
                return f"`git {sub}` discards changes"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    for tokens in segments(command):
        # Look inside wrapped commands like: bash -c "..."
        inner = [tokens[k + 1] for k, t in enumerate(tokens[:-1]) if t == "-c"]
        reason = check(tokens) or next(
            (check(sub) for t in inner for sub in segments(t) if check(sub)), None
        )
        if reason:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"Delete check: {reason}. Confirm first.",
            }}))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
