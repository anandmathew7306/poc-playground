# claude-rules

Generic steps for giving **Claude Code** the same constraints in every chat, and for
**enforcing** the ones that must never be broken.

Companion to [`../cursor-rules/`](../cursor-rules/). Same ideas, but Claude Code adds one thing
Cursor rules cannot do: hooks that actually block a command before it runs.

## Rules vs enforcement

A rule in `CLAUDE.md` is an instruction. The agent usually follows it, but it can still get
it wrong. For things that must never happen (changing a live cluster, committing client data
to a public repo), add a **hook** or a **deny rule** as well.

| Kind | Where | What it does |
|---|---|---|
| Global rules | `~/.claude/CLAUDE.md` | Loaded in every session, every folder |
| Project rules | `<repo>/CLAUDE.md` or `<repo>/.claude/CLAUDE.md` | Loaded in that project |
| Deny / ask rules | `permissions` in `~/.claude/settings.json` | Blocks (or prompts for) commands by prefix |
| Hooks | `hooks` in `~/.claude/settings.json` | Your script inspects each tool call and can block it or ask |

Cursor equivalents: `CLAUDE.md` ≈ `.cursor/rules/*.mdc` with `alwaysApply: true`.
`CLAUDE.md` can import other files with `@path/to/file.md`.

## Step 1: Write the rules

Copy [`examples/CLAUDE.md.example`](examples/CLAUDE.md.example) to `~/.claude/CLAUDE.md` and
edit it. Keep it short: one section per concern, concrete do/don't lines.

## Step 2: Add deny rules

Copy the `permissions` block from [`examples/settings.json.example`](examples/settings.json.example).

Deny rules match the **start** of a command. `Bash(oc apply:*)` blocks `oc apply -f x`, but
not `oc -n foo apply -f x` or `cd x && oc apply ...`. That gap is why hooks exist.

## Step 3: Add hooks

Hooks get the tool call as JSON on stdin. Exit code `2` blocks the call and shows stderr to
the agent. Printing a `permissionDecision: "ask"` JSON makes Claude Code prompt the user.

| Hook | Does |
|---|---|
| [`block-cluster-writes.py`](examples/hooks/block-cluster-writes.py) | Blocks `oc`/`kubectl`/`helm`/`argocd`/`terraform` write verbs anywhere in a command, including after flags, `&&`, `$(...)`, and `bash -c` |
| [`confirm-deletes.py`](examples/hooks/confirm-deletes.py) | Asks before `rm`, `find -delete`, `git clean`, `git reset --hard`, etc. Claude's own temp folder is exempt |
| [`check-git-identity.py`](examples/hooks/check-git-identity.py) | Blocks commits with the wrong email for the folder, asks before every push, and blocks all history writes under `~/work/` |
| [`protect-repos.py`](examples/hooks/protect-repos.py) | Looks up repo visibility on GitHub (`gh`, cached a day; unknown = public). Scans commits to public repos for client markers and secrets. Blocks edits in reference-only repos |

Install:

```bash
mkdir -p ~/.claude/hooks
cp examples/hooks/*.py ~/.claude/hooks/ && chmod +x ~/.claude/hooks/*.py
cp examples/hooks/client-markers.txt.example ~/.claude/hooks/client-markers.txt
# edit the folder/email table in check-git-identity.py,
# the REFERENCE_ONLY list in protect-repos.py, and client-markers.txt
```

Then merge the `hooks` block from `settings.json.example` into `~/.claude/settings.json`.

## Step 4: Test the hooks

Feed a fake tool call in and check the result:

```bash
echo '{"tool_input":{"command":"oc -n demo delete pod x"}}' \
  | ~/.claude/hooks/block-cluster-writes.py; echo "exit=$?"   # expect exit=2
echo '{"tool_input":{"command":"oc get pods"}}' \
  | ~/.claude/hooks/block-cluster-writes.py; echo "exit=$?"   # expect exit=0
```

Test both directions: commands that must be blocked, and everyday commands that must not be.
A hook that blocks too much gets switched off.

## Known gaps

- Hooks see the command text only. A script written to a file and then run is not inspected.
- Word matching can block harmless commands (e.g. writing a file whose text mentions
  `oc adm`). Use the file editing tool instead of a shell heredoc in that case.
- The strongest lock on a cluster is a read-only login. Hooks are a second layer.

## Layout

```text
claude-rules/
  README.md                 ← these steps
  examples/
    CLAUDE.md.example       ← global rules template
    settings.json.example   ← deny rules + hook wiring
    hooks/                  ← hook scripts + client-markers template
```
