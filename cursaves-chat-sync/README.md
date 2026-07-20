# cursaves — Fedora ↔ Ubuntu Cursor chat sync

Private remote: `anandmathew7306/cursaves-chats`  
Tool: [cursaves](https://github.com/Callum-Ward/cursaves)

Sync store is `~/.cursaves/` (not a browse clone of the GitHub repo).

## Fedora (done)

```bash
# install
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv tool install git+https://github.com/Callum-Ward/cursaves.git

# init + push
cursaves init --remote https://github.com/anandmathew7306/cursaves-chats.git
cursaves workspaces
cursaves push -w N --all    # or: cursaves push --ahead --all
```

## Ubuntu (home)

Same projects help (matching `git remote` URLs). Prefer Cursor quit before pull.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv tool install git+https://github.com/Callum-Ward/cursaves.git

cursaves init --remote https://github.com/anandmathew7306/cursaves-chats.git
cursaves workspaces
# import into matching project (cd there, or -w / -s)
cd /path/to/same-project && cursaves pull
# Fully quit + reopen Cursor (Reload Window is not enough)
```

Daily either machine: `cursaves sync` → restart Cursor after imports.

## Rollback

```bash
uv tool uninstall cursaves
rm -rf ~/.cursaves ~/.config/cursaves
# optional: rm -rf ~/Personal/cursaves-chats
# optional: gh repo delete anandmathew7306/cursaves-chats --yes
```

Does not delete chats already in Cursor unless you use `cursaves purge`.
