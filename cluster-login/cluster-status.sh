#!/usr/bin/env bash
# Show the active cluster login in a yellow box. Does not print tokens or passwords.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [[ -z "${CLUSTER_LOGIN_CONFIG:-}" ]]; then
    if [[ -n "${SCRIPTS:-}" && -f "$SCRIPTS/cluster-login.yaml" ]]; then
        CLUSTER_LOGIN_CONFIG="$SCRIPTS/cluster-login.yaml"
    elif [[ -f "$HOME/.scripts/cluster-login.yaml" ]]; then
        CLUSTER_LOGIN_CONFIG="$HOME/.scripts/cluster-login.yaml"
    else
        CLUSTER_LOGIN_CONFIG="$SCRIPT_DIR/clusters.yaml"
    fi
fi
export CLUSTER_LOGIN_CONFIG
KUBECONFIG_PATH="${KUBECONFIG:-$HOME/.kube/config}"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    cat <<'EOF'
Usage: cluster-status

Show the active cluster login (company, cluster, user, server).
EOF
    exit 0
fi

python3 - "$CLUSTER_LOGIN_CONFIG" "$KUBECONFIG_PATH" <<'PY'
import os, subprocess, sys, yaml
from pathlib import Path

catalog_path = Path(sys.argv[1])
kube_path = Path(sys.argv[2]).expanduser()
use_color = os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"
RESET = "\033[0m"
YELLOW = "\033[1;33m"
DIM = "\033[2m"
MIN_WIDTH = 40


def paint(code, text):
    if not use_color:
        return text
    return code + text + RESET


def dim_box(s):
    return paint(DIM, s)


def load_yaml(path):
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def oc(*args, timeout=3):
    try:
        r = subprocess.run(
            ["oc", *args],
            env=dict(os.environ, KUBECONFIG=str(kube_path)),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""
    if r.returncode != 0:
        return ""
    return r.stdout.strip()


def display_user(raw):
    if not raw:
        return "-"
    if "/" in raw:
        left, right = raw.split("/", 1)
        if right.startswith("api") or ":6443" in right or ":443" in right:
            return left
    return raw


catalog = load_yaml(catalog_path)
kube = load_yaml(kube_path)
clients = catalog.get("clients") or {}

entries = []
for client, spec in clients.items():
    grouped = spec.get("groups") or {}
    if grouped:
        cluster_lists = []
        for clist in grouped.values():
            cluster_lists.extend(clist or [])
    else:
        cluster_lists = (spec or {}).get("clusters") or []
    for cluster in cluster_lists:
        server = cluster.get("server") or ""
        kc = cluster.get("kubeconfig") or ""
        if kc and not server:
            extra = load_yaml(Path(os.path.expanduser(kc)))
            for item in extra.get("clusters") or []:
                server = (item.get("cluster") or {}).get("server") or server
        entries.append(
            {
                "company": client,
                "name": cluster.get("name") or cluster.get("id") or "",
                "server": server.rstrip("/"),
                "context": "%s-%s" % (client.lower(), cluster.get("id") or ""),
            }
        )

clusters_by_name = {}
for item in kube.get("clusters") or []:
    clusters_by_name[item.get("name")] = ((item.get("cluster") or {}).get("server") or "").rstrip("/")

current = kube.get("current-context") or ""
active = None
for item in kube.get("contexts") or []:
    if item.get("name") != current:
        continue
    ctx = item.get("context") or {}
    cluster_name = ctx.get("cluster") or ""
    server = clusters_by_name.get(cluster_name) or ""
    entry = None
    for cand in entries:
        if cand["context"] == current:
            entry = cand
            break
    if entry is None and server:
        for cand in entries:
            if cand["server"] and cand["server"] == server:
                entry = cand
                break
    company = entry["company"] if entry else "-"
    cluster = entry["name"] if entry else current or "-"
    user = display_user(ctx.get("user") or "")
    if not server and entry:
        server = entry["server"]
    active = {
        "company": company,
        "cluster": cluster,
        "user": user,
        "server": server or "-",
    }
    break

if active:
    live_user = oc("whoami")
    if live_user:
        active["user"] = live_user
    live_server = oc("whoami", "--show-server")
    if live_server:
        active["server"] = live_server

if not current or not active:
    lines = ["Not logged in"]
else:
    lines = [
        "Company : %s" % active["company"],
        "Cluster : %s" % active["cluster"],
        "User    : %s" % active["user"],
        "Server  : %s" % active["server"],
    ]

tw = max(MIN_WIDTH, max(len(x) for x in lines))
try:
    cols = os.get_terminal_size().columns
    if cols > 24:
        tw = min(tw, cols - 4)
except OSError:
    pass

clipped = []
for line in lines:
    if len(line) > tw:
        line = line[: tw - 1] + "…"
    clipped.append(line.ljust(tw))

between = tw + 2
print(dim_box("┌" + "─" * between + "┐"))
for line in clipped:
    print(dim_box("│ ") + paint(YELLOW, line) + dim_box(" │"))
print(dim_box("└" + "─" * between + "┘"))
PY
python3 "$SCRIPT_DIR/cluster_ui.py" vpn
