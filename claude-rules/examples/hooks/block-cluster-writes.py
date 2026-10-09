#!/usr/bin/env python3
"""PreToolUse hook: block any shell command that could change a live cluster.

Reads the Claude Code hook JSON on stdin. Exit 2 = block (stderr is shown to Claude).
"""
import json
import re
import shlex
import sys

# Tool -> verbs that are blocked. "*" means the tool is blocked entirely.
BLOCKED = {
    "oc": {
        "create", "apply", "edit", "patch", "replace", "delete", "scale", "label",
        "annotate", "rollout", "drain", "cordon", "uncordon", "taint", "exec", "rsh",
        "rsync", "debug", "cp", "port-forward", "attach", "proxy", "run", "expose",
        "autoscale", "set", "adm", "new-app", "new-project", "new-build",
        "start-build", "cancel-build", "import-image", "tag", "extract",
    },
    "kubectl": {
        "create", "apply", "edit", "patch", "replace", "delete", "scale", "label",
        "annotate", "rollout", "drain", "cordon", "uncordon", "taint", "exec",
        "debug", "cp", "port-forward", "attach", "proxy", "run", "expose",
        "autoscale", "set", "certificate",
    },
    "helm": {"install", "upgrade", "uninstall", "delete", "rollback", "plugin"},
    "argocd": {
        "sync", "delete", "create", "set", "unset", "patch", "rollback", "edit",
        "terminate-op", "run", "add", "rm",
    },
    "terraform": {"apply", "destroy", "import", "taint", "untaint", "rm", "mv", "push"},
    "tofu": {"apply", "destroy", "import", "taint", "untaint", "rm", "mv", "push"},
    "ansible-playbook": "*",
}

# Prints the login token.
TOKEN_FLAGS = {"-t", "--show-token"}


def segments(command):
    """Split a shell command into simple-command token lists."""
    # Break on shell separators so `cd x && oc apply` is checked per part.
    parts = re.split(r"\|\||&&|[;|&\n]|\$\(|`|\(|\)", command)
    for part in parts:
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            tokens = part.split()
        if tokens:
            yield tokens


def check(tokens):
    for i, tok in enumerate(tokens):
        tool = tok.rsplit("/", 1)[-1]
        if tool not in BLOCKED:
            continue
        rest = tokens[i + 1:]
        verbs = BLOCKED[tool]
        if verbs == "*":
            return f"`{tool}` is blocked"
        if tool == "oc" and "whoami" in rest and TOKEN_FLAGS & set(rest):
            return "`oc whoami -t` prints the login token"
        hit = next((t for t in rest if t in verbs), None)
        if hit:
            return f"`{tool} ... {hit}` can change a live cluster"
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
            print(
                f"BLOCKED by live-cluster lock: {reason}. Do not run it. "
                "Give the user the exact command and let them run it themselves.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
