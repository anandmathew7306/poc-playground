#!/usr/bin/env python3
"""PreToolUse hook: ask before any cloud CLI command that is not read-only.

Uses an allowlist: known read-only actions run; everything else (including actions this
script has never seen) asks the user. Commands that print secrets also ask.
"""
import json
import re
import shlex
import sys

WRAPPERS = {"sudo", "xargs", "exec", "nohup", "time", "command", "env", "nice", "watch"}
# Global options that take a value, so the value is not mistaken for a service/action.
VALUE_OPTS = {
    "aws": {"--region", "--profile", "--output", "--query", "--endpoint-url", "--color",
            "--ca-bundle", "--cli-read-timeout", "--cli-connect-timeout"},
    "linode-cli": {"--format", "--delimiter", "--page", "--page-size", "--as-user",
                   "--api-version", "--config"},
}
READ_WORDS = {"list", "view", "ls", "la", "du", "show", "describe", "whoami", "version",
              "help", "info"}


def segments(command):
    parts = re.split(r"\|\||&&|[;|&\n]|\$\(|`|\(|\)", command)
    for part in parts:
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            tokens = part.split()
        if tokens:
            yield tokens


def positionals(tool, args):
    """Leading service/group/action words, skipping global options and their values."""
    pos, i, opts = [], 0, VALUE_OPTS.get(tool, set())
    while i < len(args):
        a = args[i]
        if a in opts:
            i += 2
            continue
        if a.startswith("-"):
            if pos:  # action flags start here
                break
            i += 1
            continue
        pos.append(a)
        i += 1
    return pos


def check_aws(args):
    pos = positionals("aws", args)
    if len(pos) < 2:
        return None  # e.g. `aws --version`, `aws help`
    service, action = pos[0], pos[1]
    if (service == "secretsmanager" and action == "get-secret-value") or \
       (service == "ssm" and action.startswith("get-parameter") and "--with-decryption" in args) or \
       (service == "ecr" and action == "get-login-password"):
        return f"`aws {service} {action}` prints a secret"
    if action.startswith(("describe-", "list-", "get-", "lookup-", "search-")) or \
       action in {"help", "wait"} or (service == "s3" and action == "ls") or \
       (service == "configure" and action in {"list", "get"}):
        return None
    return f"`aws {service} {action}` may change cloud resources"


def check_linode(args):
    pos = positionals("linode-cli", args)
    if len(pos) < 2:
        return None if not pos or pos[0] in READ_WORDS else \
            f"`linode-cli {pos[0]}` may change settings"
    group, action = pos[0], pos[1]
    if re.search(r"kubeconfig|creds|token|secret", action):
        return f"`linode-cli {group} {action}` may print a secret"
    if action in READ_WORDS or action.endswith(("-list", "-view")):
        return None
    return f"`linode-cli {group} {action}` may change cloud resources"


def check_generic(tool, args):
    pos = positionals(tool, args)
    if not pos:
        return None
    text = " ".join(pos)
    if re.search(r"token|credential|password|secret|kubeconfig", text):
        return f"`{tool} {text}` may print a secret"
    words = pos[:1] if tool == "rosa" else pos
    if any(w in READ_WORDS for w in words):
        return None
    return f"`{tool} {text}` may change cloud resources"


CHECKS = {
    "aws": check_aws,
    "linode-cli": check_linode,
    "rosa": lambda a: check_generic("rosa", a),
    "az": lambda a: check_generic("az", a),
    "gcloud": lambda a: check_generic("gcloud", a),
}


def check(tokens):
    i = 0
    while i < len(tokens) and ("=" in tokens[i] or tokens[i] in WRAPPERS
                               or (i and tokens[i].startswith("-"))):
        i += 1
    if i >= len(tokens):
        return None
    tool = tokens[i].rsplit("/", 1)[-1]
    return CHECKS[tool](tokens[i + 1:]) if tool in CHECKS else None


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
                "permissionDecisionReason": f"Cloud check: {reason}. Confirm first.",
            }}))
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
