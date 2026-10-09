#!/usr/bin/env python3
"""PreToolUse hook: keep client data and secrets out of public repos.

- Reference-only repos: no edits and no git history writes at all.
- `git commit` in a PUBLIC repo: scan the changes being committed (and the message)
  for client markers and secrets. Any hit blocks the commit (exit 2).
- Visibility comes from GitHub (cached for a day). Unknown = treated as public.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
HOOKS = os.path.dirname(os.path.abspath(__file__))
MARKERS_FILE = os.path.join(HOOKS, "client-markers.txt")
CACHE_FILE = os.path.join(HOME, ".claude", "cache", "repo-visibility.json")
CACHE_TTL = 24 * 3600

REFERENCE_ONLY = [f"{HOME}/personal/reference-repo/"]
HISTORY_WRITES = {"commit", "push", "merge", "rebase", "cherry-pick", "revert", "am",
                  "tag", "pull", "reset"}

SECRETS = [
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bghp_[A-Za-z0-9]{20,}", r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bglpat-[A-Za-z0-9_-]{20,}", r"\bAKIA[0-9A-Z]{16}\b", r"\bsha256~[A-Za-z0-9_-]{20,}",
    r"\bxox[abp]-[A-Za-z0-9-]{10,}",
    # key: value where the value looks real (not a <placeholder>, $VAR, or example)
    r"(?i)\b(password|passwd|secret|token|api[_-]?key)\b[\"']?\s*[:=]\s*[\"']?"
    r"(?![<$\{]|x{3,}|\*{3,}|changeme|example|your|redacted)[^\s\"']{8,}",
]


def segments(command):
    parts = re.split(r"\|\||&&|[;|&\n]|\$\(|`|\(|\)", command)
    for part in parts:
        try:
            tokens = shlex.split(part, posix=True)
        except ValueError:
            tokens = part.split()
        if tokens:
            yield tokens


def under(path, prefixes):
    path = os.path.realpath(path) + "/"
    return any(path.startswith(p) for p in prefixes)


def git(repo, *args):
    try:
        out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                             timeout=10)
        return out.stdout if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def visibility(repo):
    """Return 'PRIVATE' or 'PUBLIC'. Anything unknown counts as PUBLIC."""
    url = git(repo, "remote", "get-url", "origin").strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if not m:
        return "PUBLIC"
    slug = m.group(1)
    try:
        cache = json.load(open(CACHE_FILE))
    except (OSError, ValueError):
        cache = {}
    hit = cache.get(slug)
    if hit and time.time() - hit["at"] < CACHE_TTL:
        return hit["vis"]
    try:
        out = subprocess.run(["gh", "repo", "view", slug, "--json", "visibility",
                              "-q", ".visibility"], capture_output=True, text=True, timeout=15)
        vis = out.stdout.strip().upper()
    except (OSError, subprocess.SubprocessError):
        vis = ""
    if vis not in {"PUBLIC", "PRIVATE"}:
        return "PUBLIC"
    cache[slug] = {"vis": vis, "at": time.time()}
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        json.dump(cache, open(CACHE_FILE, "w"), indent=1)
    except OSError:
        pass
    return vis


def load_patterns():
    pats = []
    try:
        for line in open(MARKERS_FILE):
            line = line.strip()
            if line and not line.startswith("#"):
                pats.append(("client marker", re.compile(line, re.I)))
    except OSError:
        pass
    pats += [("possible secret", re.compile(p)) for p in SECRETS]
    return pats


def added_lines(repo, include_unstaged):
    """Yield (file, text) for lines that this commit would add."""
    diffs = [git(repo, "diff", "--cached", "-U0", "--no-color")]
    if include_unstaged:
        diffs.append(git(repo, "diff", "-U0", "--no-color"))
        for f in git(repo, "ls-files", "--others", "--exclude-standard").splitlines():
            try:
                with open(os.path.join(repo, f), errors="ignore") as fh:
                    for line in fh:
                        yield f, line.rstrip("\n")
            except OSError:
                pass
    for diff in diffs:
        current = "?"
        for line in diff.splitlines():
            if line.startswith("+++ "):
                current = line[6:] if line.startswith("+++ b/") else line[4:]
            elif line.startswith("+") and not line.startswith("+++"):
                yield current, line[1:]


def scan(repo, include_unstaged, message):
    pats = load_patterns()
    hits = []
    lines = list(added_lines(repo, include_unstaged))
    lines += [("(commit message)", m) for m in message]
    for f, text in lines:
        for kind, pat in pats:
            if pat.search(text):
                hits.append(f"  {f}: [{kind}] {text.strip()[:120]}")
                break
    return hits


def block(reason):
    print(f"BLOCKED by repo protection: {reason}", file=sys.stderr)
    return 2


def check_edit(data):
    path = (data.get("tool_input") or {}).get("file_path") or \
           (data.get("tool_input") or {}).get("notebook_path") or ""
    if path and under(os.path.dirname(path) or ".", REFERENCE_ONLY):
        return block(f"{path} is in a reference-only repo. Do not edit it. "
                     "Work in your own repo instead.")
    return 0


def check_bash(data):
    command = (data.get("tool_input") or {}).get("command", "")
    cwd = data.get("cwd") or os.getcwd()
    staged_now = False  # a `git add` earlier in the same command
    for tokens in segments(command):
        if tokens[0] == "cd" and len(tokens) > 1:
            cwd = os.path.join(cwd, os.path.expanduser(tokens[1]))
            continue
        if "git" not in tokens:
            continue
        args = tokens[tokens.index("git") + 1:]
        repo, i, sub = cwd, 0, None
        while i < len(args):
            a = args[i]
            if a in ("-C", "-c") and i + 1 < len(args):
                if a == "-C":
                    repo = os.path.join(repo, os.path.expanduser(args[i + 1]))
                i += 2
                continue
            if a.startswith("-"):
                i += 1
                continue
            sub = a
            break
        rest = args[i + 1:]
        if sub == "add":
            staged_now = True
            continue
        if sub in HISTORY_WRITES and under(repo, REFERENCE_ONLY):
            return block(f"`git {sub}` in a reference-only repo. Work in your own repo instead.")
        if sub != "commit" or under(repo, [f"{HOME}/work/"]):
            continue
        top = git(repo, "rev-parse", "--show-toplevel").strip()
        if not top or visibility(top) == "PRIVATE":
            continue
        # -a, --all, or combined short flags like -am
        all_flag = any(r == "--all" or re.fullmatch(r"-[a-zA-Z]*a[a-zA-Z]*", r) for r in rest)
        message = [rest[k + 1] for k, r in enumerate(rest[:-1]) if r in ("-m", "--message")]
        hits = scan(top, staged_now or all_flag, message)
        if hits:
            shown = "\n".join(hits[:15]) + (f"\n  ... and {len(hits) - 15} more" if len(hits) > 15 else "")
            return block(f"{os.path.basename(top)} is a PUBLIC repo and the commit contains "
                         f"client data or secrets:\n{shown}\nRemove or genericise these, "
                         "then show the user before retrying.")
    return 0


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") in ("Edit", "Write", "NotebookEdit"):
        return check_edit(data)
    return check_bash(data)


if __name__ == "__main__":
    sys.exit(main())
