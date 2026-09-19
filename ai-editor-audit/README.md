# ai-editor-audit

Read-only look at **Cursor** and **Claude Code** on this machine: how they
were installed, which data dirs exist, and which project-level config
files are git-tracked vs local-only.

Tested against package-manager / native installs on Fedora (`dnf`) and
Ubuntu (`apt`). Flatpak / Snap / AppImage paths are not covered.

**Read-only.** These scripts do not uninstall or delete anything.

## Usage

```bash
./audit.sh
./find-project-configs.sh
./find-project-configs.sh ~/Personal ~/Work
```

`find-project-configs.sh` defaults to the current directory. Pass roots
explicitly if you want a wider scan.

## What they report

| Script | Output |
|---|---|
| `audit.sh` | Package manager, package/binary, repo file, data-dir sizes |
| `find-project-configs.sh` | `.cursor`, `.claude`, `.mcp.json`, `.cursorrules` plus git status |

`TRACKED` means the path is committed — treat it as shared repo content.
`gitignored` / `untracked` means it is local to this clone.

Save live paths and sizes in a private notes repo. This folder is safe
for a public tree (generic scripts only).
