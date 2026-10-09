#!/usr/bin/env python3
"""PreToolUse hook: check git identity before commit, and ask before push.

- Under ~/work, anything that writes git history is blocked. The user commits.
- `git commit` with the wrong email for the folder is blocked (exit 2).
- `git push` always asks the user first.
"""
import json
import os
import re
import shlex
import subprocess
import sys

HOME = os.path.expanduser("~")
# Folder prefix -> required commit email. Longest match wins.
IDENTITY = {
    f"{HOME}/personal/": "you@example.com",
    f"{HOME}/work/client-a/": "you@client-a.example",
    f"{HOME}/work/client-b/": "you@client-b.example",
}
# In Work, the user does all commits and pushes themselves.
WORK = f"{HOME}/work/"
WORK_BLOCKED = {"commit", "push", "merge", "rebase", "cherry-pick", "revert", "am",
                "tag", "pull", "reset"}


def segments(command):
    parts = re.split(r"\|\||&&|[;|&\n]|\$\(|`|\(|\)", command)
    for part in parts:
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            tokens = part.split()
        if tokens:
            yield tokens


def expected_email(path):
    path = os.path.realpath(path) + "/"
    match = max((p for p in IDENTITY if path.startswith(p)), key=len, default=None)
    return IDENTITY.get(match)


def git_email(path):
    try:
        out = subprocess.run(["git", "-C", path, "config", "user.email"],
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def ask(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }}))
    return 0


def block(reason):
    print(f"BLOCKED by git identity check: {reason}", file=sys.stderr)
    return 2


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (data.get("tool_input") or {}).get("command", "")
    cwd = data.get("cwd") or os.getcwd()

    for tokens in segments(command):
        # Track `cd dir` so `cd repo && git commit` checks the right folder.
        if tokens[0] == "cd" and len(tokens) > 1:
            cwd = os.path.join(cwd, os.path.expanduser(tokens[1]))
            continue
        env_email = next((t.split("=", 1)[1] for t in tokens
                          if t.startswith(("GIT_AUTHOR_EMAIL=", "GIT_COMMITTER_EMAIL="))), None)
        if "git" not in tokens:
            continue
        args = tokens[tokens.index("git") + 1:]
        repo, override, sub = cwd, env_email, None
        i = 0
        while i < len(args):
            a = args[i]
            if a == "-C" and i + 1 < len(args):
                repo = os.path.join(repo, os.path.expanduser(args[i + 1])); i += 2; continue
            if a == "-c" and i + 1 < len(args):
                if args[i + 1].startswith("user.email="):
                    override = args[i + 1].split("=", 1)[1]
                i += 2; continue
            if a.startswith("-"):
                i += 1; continue
            sub = a
            break
        rest = args[i + 1:]

        if sub in WORK_BLOCKED and (os.path.realpath(repo) + "/").startswith(WORK):
            return block(f"`git {sub}` in the Work folder. The user commits and pushes "
                         "here. Suggest the commands and commit message instead.")
        if sub == "push":
            return ask("git push: confirm before pushing.")
        if sub != "commit":
            continue
        if any(r.startswith("--author") for r in rest):
            return block("do not use --author; commit with the folder's identity.")
        want = expected_email(repo)
        if not want:
            continue
        have = override or git_email(repo)
        if have != want:
            return block(f"this folder must commit as {want}, but git would use "
                         f"'{have or 'nothing'}'. Stop and tell the user.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
