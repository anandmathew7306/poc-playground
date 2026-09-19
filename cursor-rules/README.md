# cursor-rules

Generic steps for adding **Cursor project rules** so the agent keeps the same constraints in every chat.

This is not a dump of one machine’s rules. Copy the pattern, then write rules that match the folder you opened.

## What a rule is

A project rule is a Markdown file with YAML frontmatter, stored in the **workspace** as:

```text
<workspace>/.cursor/rules/<name>.mdc
```

Cursor loads those files when that folder is the workspace root (File → Open Folder on the directory that contains `.cursor/`). Opening only a nested git repo will miss parent-folder rules.

Two other places people mix up:

| Kind | Where | Scope |
|---|---|---|
| Project rules | `.cursor/rules/*.mdc` | This workspace |
| User rules | Cursor Settings → Rules | Your Cursor user, every project |
| Skills | `.cursor/skills/**/SKILL.md` | Invoked for a task, not always-on |

Use **project rules** for “how we work in this tree.” Use **user rules** for habits that should follow you everywhere (commit protocol, PR style). This note covers project rules.

## Step 1 — Decide the workspace

Open the folder that should own the rules. Examples:

- a monorepo root
- `~/Work` if client trees live side by side
- `~/Personal` if public/learning trees live side by side

One concern per file. Prefer several short `.mdc` files over one long page.

## Step 2 — Choose apply mode

**Always on** (every chat in this workspace):

```yaml
---
description: One-line summary shown in the rule picker
alwaysApply: true
---
```

**Only when matching files are in play:**

```yaml
---
description: Python conventions
globs: "**/*.py"
alwaysApply: false
---
```

`globs` is a file pattern (`**/*.ts`, `charts/**/*.yaml`). If you set neither `alwaysApply: true` nor `globs`, the rule is easy to miss.

## Step 3 — Create the directory and files

```bash
mkdir -p .cursor/rules
```

Name files by concern, not by date:

```text
.cursor/rules/git-identity.mdc
.cursor/rules/no-secrets.mdc
.cursor/rules/python-style.mdc
```

Frontmatter, then a short Markdown body. Keep each file under ~50 lines, actionable, with a concrete do/don’t if it helps.

Templates live in [`examples/`](examples/). Copy, rename to `.mdc`, and replace placeholders.

```bash
cp examples/always-apply.git-identity.mdc.example .cursor/rules/git-identity.mdc
cp examples/always-apply.no-secrets.mdc.example .cursor/rules/no-secrets.mdc
# edit the copies
```

## Step 4 — Write the body

Good rules tell the agent **what to do and what not to do**:

- Git: which `user.email` / hosting account this tree uses; do not run `git config` to override it; ask before push.
- Secrets: no tokens, passwords, or private hostnames in files that will be committed.
- Live systems: read-only unless the user explicitly asks for a change.

Bad rules are vague (“be careful”) or dump a whole handbook.

Do **not** put real credentials, private URLs, or client names into a rule that will be committed to a public repo. Point at a local path instead (“passwords live in `~/.ssh/`, never in git”).

## Step 5 — Reload and check

1. Save the `.mdc` files.
2. If the agent does not pick them up, start a new chat (or reopen the folder).
3. Ask: “What project rules are you following?” The answer should mention the descriptions you set.

Cursor also has a rule picker in the UI; `alwaysApply: true` rules should show as applied for that workspace.

## Checklist

- [ ] Workspace folder is the one that contains `.cursor/rules/`
- [ ] Each file is `.mdc` with YAML frontmatter
- [ ] `alwaysApply: true` **or** a `globs` pattern
- [ ] One concern per file
- [ ] No secrets or private inventory in the rule text
- [ ] New chat sees the rules

## Optional: `AGENTS.md`

A root `AGENTS.md` is a longer human/agent brief for the repo. It does not replace `.cursor/rules/`. Use rules for hard constraints; use `AGENTS.md` for orientation (“what this repo is”).

## Layout of this PoC

```text
cursor-rules/
  README.md          ← these steps
  examples/          ← copy-paste templates (not live Cursor rules)
```

The examples are named `*.mdc.example` so this folder does not install rules into `poc-playground` itself. To try them here, copy into `poc-playground/.cursor/rules/` or into another workspace.
