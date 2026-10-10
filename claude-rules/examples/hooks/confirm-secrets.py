#!/usr/bin/env python3
"""PreToolUse hook: ask before showing secret values.

- Bash: `oc/kubectl get secret ... -o yaml|json|jsonpath|go-template`, and reading known
  credential files (kubeconfigs, cloud credentials, private keys, pull secrets, .env).
- Read / Grep tools: the same credential files and folders.
Prints a permission "ask" decision; prints nothing to let the call run.
"""
import json
import os
import re
import shlex
import sys

HOME = os.path.expanduser("~")
WRAPPERS = {"sudo", "xargs", "exec", "nohup", "time", "command", "env", "nice"}
# Commands that print or copy file contents.
READERS = {"cat", "tac", "less", "more", "head", "tail", "bat", "grep", "egrep", "rg", "awk",
           "sed", "base64", "jq", "yq", "strings", "xxd", "od", "hexdump", "cp", "scp",
           "rsync", "diff", "nl", "sort", "uniq", "cut", "tr", "openssl"}
CRED_DIRS = [f"{HOME}/.kube", f"{HOME}/.aws", f"{HOME}/.ssh", f"{HOME}/.config/linode-cli",
             f"{HOME}/.docker", f"{HOME}/.config/gh"]
CRED_FILES = {f"{HOME}/.aws/credentials", f"{HOME}/.git-credentials", f"{HOME}/.netrc",
              f"{HOME}/.pgpass", f"{HOME}/.claude/.credentials.json",
              f"{HOME}/.docker/config.json", f"{HOME}/.config/gh/hosts.yml"}
SECRET_OUTPUT = re.compile(r"^(yaml|json|jsonpath.*|go-template.*|template.*)$")


def segments(command):
    parts = re.split(r"\|\||&&|[;|&\n]|\$\(|`|\(|\)", command)
    for part in parts:
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            tokens = part.split()
        if tokens:
            yield tokens


def cred_path(path, allow_dirs=False):
    """Return a reason if this path is a credential file (or folder)."""
    if not path:
        return None
    p = os.path.normpath(os.path.expanduser(path))
    name = os.path.basename(p).lower()
    if p in CRED_FILES or p.startswith(f"{HOME}/.kube/") or \
       p.startswith(f"{HOME}/.config/linode-cli"):
        return f"{path} holds credentials"
    if p.startswith(f"{HOME}/.ssh/") and name.startswith("id_") and not name.endswith(".pub"):
        return f"{path} is a private key"
    if allow_dirs and p in CRED_DIRS:
        return f"{path} holds credentials"
    if re.search(r"example|sample|template", name):
        return None
    if "kubeconfig" in name or "pull-secret" in name or name == "kubeadmin-password" or \
       name == ".env" or name.startswith(".env.") or name.endswith((".env", ".key")):
        return f"{path} looks like a credential file"
    return None


def output_value(rest):
    for k, r in enumerate(rest):
        if r in ("-o", "--output") and k + 1 < len(rest):
            return rest[k + 1]
        if r.startswith("--output="):
            return r.split("=", 1)[1]
        if r.startswith("-o") and len(r) > 2:
            return r[2:].lstrip("=")
    return ""


def check(tokens):
    i = 0
    while i < len(tokens) and ("=" in tokens[i] or tokens[i] in WRAPPERS
                               or (i and tokens[i].startswith("-"))):
        i += 1
    if i >= len(tokens):
        return None
    tool = tokens[i].rsplit("/", 1)[-1]
    rest = tokens[i + 1:]
    if tool in ("oc", "kubectl") and "get" in rest:
        is_secret = any(re.match(r"^secrets?(/|$)", r) or
                        ("," in r and re.search(r"(^|,)secrets?(,|$)", r)) for r in rest)
        if is_secret and SECRET_OUTPUT.match(output_value(rest)):
            return f"`{tool} get secret -o {output_value(rest)}` prints secret values"
    if tool in READERS:
        for r in rest:
            if not r.startswith("-"):
                reason = cred_path(r, allow_dirs=tool in ("grep", "egrep", "rg"))
                if reason:
                    return reason
    return None


def ask(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": f"Secret check: {reason}. Confirm first.",
    }}))
    return 0


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    tool_input = data.get("tool_input") or {}
    if data.get("tool_name") in ("Read", "Grep"):
        reason = cred_path(tool_input.get("file_path") or tool_input.get("path"),
                           allow_dirs=True)
        return ask(reason) if reason else 0
    command = tool_input.get("command", "")
    for tokens in segments(command):
        inner = [tokens[k + 1] for k, t in enumerate(tokens[:-1]) if t == "-c"]
        reason = check(tokens) or next(
            (check(sub) for t in inner for sub in segments(t) if check(sub)), None
        )
        if reason:
            return ask(reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
