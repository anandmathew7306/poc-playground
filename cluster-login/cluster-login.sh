#!/usr/bin/env bash
# Pick a client, then a cluster, then log in with oc.
# Arrow-key menus stay in this terminal (no full-screen UI).
# Catalog path: $CLUSTER_LOGIN_CONFIG (YAML). Passwords are never read from that file.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  cluster-login                      Interactive client → cluster → oc login
  cluster-login CLIENT               Pick a cluster for CLIENT
  cluster-login CLIENT CLUSTER_ID    Log in to that cluster
  cluster-login set-password [CLIENT]
  cluster-login list
  cluster-login status
  cluster-login --dry-run [CLIENT [CLUSTER_ID]]

Config: $CLUSTER_LOGIN_CONFIG (YAML). See clusters.yaml.example.
Passwords live in ~/.ssh/.<client>_pass (same place as .work_proxy_pass), not in the catalog.
EOF
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DEFAULT_CONFIG="${CLUSTER_LOGIN_CONFIG:-}"
if [[ -z "$DEFAULT_CONFIG" ]]; then
    if [[ -n "${SCRIPTS:-}" && -f "$SCRIPTS/cluster-login.yaml" ]]; then
        DEFAULT_CONFIG="$SCRIPTS/cluster-login.yaml"
    elif [[ -f "$HOME/.scripts/cluster-login.yaml" ]]; then
        DEFAULT_CONFIG="$HOME/.scripts/cluster-login.yaml"
    else
        DEFAULT_CONFIG="$SCRIPT_DIR/clusters.yaml"
    fi
fi
CONFIG=$DEFAULT_CONFIG
KUBECONFIG_PATH="${KUBECONFIG:-$HOME/.kube/config}"
DRY_RUN=0

cfg() {
    python3 - "$CONFIG" "$@" <<'PY'
import json, sys, yaml
from pathlib import Path

path = Path(sys.argv[1])
cmd = sys.argv[2]
args = sys.argv[3:]
data = yaml.safe_load(path.read_text()) or {}
clients = data.get("clients") or {}

def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)

def find_client(name):
    for key, spec in clients.items():
        if key.lower() == name.lower():
            return key, spec or {}
    die("Unknown client %r. Choose: %s" % (name, ", ".join(clients) or "(none)"))

def grouped_clusters(spec):
    groups = spec.get("groups") or {}
    if groups:
        out = []
        for gname, clist in groups.items():
            for c in clist or []:
                item = dict(c)
                item["_group"] = gname
                out.append(item)
        return out
    return [dict(c) for c in spec.get("clusters") or []]

def clusters_in_group(spec, group):
    if not group:
        return grouped_clusters(spec)
    groups = spec.get("groups") or {}
    for gname, clist in groups.items():
        if gname.lower() == group.lower():
            return [dict(c, _group=gname) for c in clist or []]
    die("Unknown environment %r. Choose: %s" % (group, ", ".join(groups) or "(none)"))

def attach_client_defaults(client, spec, cluster):
    cluster = dict(cluster)
    cluster["_client"] = client
    cluster["_username"] = cluster.get("username") or spec.get("username") or ""
    cluster["_password_file"] = cluster.get("password_file") or spec.get("password_file") or ""
    if "insecure_skip_tls_verify" not in cluster and "insecure_skip_tls_verify" in spec:
        cluster["insecure_skip_tls_verify"] = spec.get("insecure_skip_tls_verify")
    return cluster

if cmd == "clients":
    for name in clients:
        print(name)
elif cmd == "groups":
    client, spec = find_client(args[0])
    for name in spec.get("groups") or {}:
        print(name)
elif cmd == "cluster-ids":
    client, spec = find_client(args[0])
    group = args[1] if len(args) > 1 else ""
    for c in clusters_in_group(spec, group):
        print(c.get("id", ""))
elif cmd == "cluster-labels":
    client, spec = find_client(args[0])
    group = args[1] if len(args) > 1 else ""
    for c in clusters_in_group(spec, group):
        print(c.get("name") or c.get("id", ""))
elif cmd == "cluster-json":
    client, spec = find_client(args[0])
    wanted = args[1]
    group = args[2] if len(args) > 2 else ""
    pool = clusters_in_group(spec, group)
    found = None
    matches = []
    for c in pool:
        if c.get("id") == wanted or c.get("name") == wanted:
            matches.append(c)
    if len(matches) == 1:
        found = matches[0]
    elif len(matches) > 1:
        die("Ambiguous cluster %r. Use the id." % wanted)
    if not found:
        ids = ", ".join(c.get("id", "?") for c in pool)
        die("Unknown cluster %r for %s. Choose: %s" % (wanted, client, ids or "(none)"))
    print(json.dumps(attach_client_defaults(client, spec, found)))
elif cmd == "list":
    for client, spec in clients.items():
        print(client)
        groups = spec.get("groups") or {}
        if groups:
            for gname, clist in groups.items():
                print("  %s" % gname)
                for c in clist or []:
                    print("    %-16s %s" % (c.get("id", ""), c.get("name", "")))
        else:
            for c in spec.get("clusters") or []:
                print("  %-16s %s" % (c.get("id", ""), c.get("name", "")))
            if not groups and not (spec.get("clusters") or []):
                print("  (none yet)")
else:
    die("unknown cfg command")
PY
}

ensure_config() {
    if [[ ! -f "$CONFIG" ]]; then
        echo "Missing catalog: $CONFIG" >&2
        echo "Copy clusters.yaml.example and set CLUSTER_LOGIN_CONFIG, or place it next to this script." >&2
        exit 1
    fi
}

# Inline arrow-key menu on this terminal (no alternate screen).
# Prints the chosen line to stdout, or __QUIT__.
pick() {
    local title=$1
    shift
    local options=("$@")
    if [[ ${#options[@]} -eq 0 ]]; then
        echo "Nothing to choose for: $title" >&2
        exit 1
    fi
    python3 - "$title" "${options[@]}" <<'PY'
import os, select, sys, termios, tty

title = sys.argv[1]
base = sys.argv[2:]
if not base:
    print("No options", file=sys.stderr)
    sys.exit(1)

items = list(base)
items.append("Quit")
n_main = len(base)

try:
    tty_in = open("/dev/tty", "rb", buffering=0)
    tty_out = open("/dev/tty", "w", buffering=1)
except OSError:
    print("Need a terminal for the menu, or pass CLIENT CLUSTER_ID", file=sys.stderr)
    sys.exit(1)

idx = 0
drawn = 0
fd = tty_in.fileno()
use_color = os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"
RESET = "\033[0m"
LIGHT_BLUE = "\033[38;5;117m"
SEL = "\033[0;30;48;5;117m"
RED = "\033[31m"
DIM = "\033[2m"


def paint(code, text):
    if not use_color:
        return text
    return code + text + RESET


def write(s):
    tty_out.write(s)
    tty_out.flush()


def text_width():
    header = title.rstrip(":").strip()
    if header:
        summaries = ["%s : %s" % (header, x) for x in items]
    else:
        summaries = list(items)
    widest = max(
        40,
        len(header),
        max(len(x) + 2 for x in items),
        max(len(s) for s in summaries),
    )
    try:
        cols = os.get_terminal_size(tty_out.fileno()).columns
        if cols > 24:
            widest = min(widest, cols - 4)
    except OSError:
        pass
    return widest


def dim_box(s):
    return paint(DIM, s)


def draw():
    global drawn
    header = title.rstrip(":").strip()
    tw = text_width()
    between = tw + 2
    if header:
        prefix = "─ %s " % header
        if len(prefix) > between:
            header = header[: max(1, between - 4)]
            prefix = "─ %s " % header
        fill = "─" * (between - len(prefix))
        top = dim_box("┌") + dim_box("─ ") + paint(LIGHT_BLUE, header) + dim_box(" " + fill + "┐")
    else:
        top = dim_box("┌" + "─" * between + "┐")
    div = dim_box("├" + "─" * between + "┤")
    bot = dim_box("└" + "─" * between + "┘")

    rows = [top]
    for i, opt in enumerate(items):
        if i == n_main:
            rows.append(div)
        marker = "▸ " if i == idx else "  "
        body = marker + opt
        if len(body) > tw:
            body = body[: tw - 1] + "…"
        padded = body.ljust(tw)
        if i == idx:
            inner = paint(SEL, padded)
        elif opt == "Quit":
            inner = paint(RED, padded)
        else:
            inner = padded
        rows.append(dim_box("│ ") + inner + dim_box(" │"))
    rows.append(bot)

    if drawn:
        write("\033[%dA" % drawn)
    for row in rows:
        write("\033[2K" + row + "\n")
    drawn = len(rows)


def boxed_line(text, color):
    tw = text_width()
    body = text
    if len(body) > tw:
        body = body[: tw - 1] + "…"
    padded = body.ljust(tw)
    between = tw + 2
    return (
        dim_box("┌" + "─" * between + "┐")
        + "\n"
        + dim_box("│ ")
        + paint(color, padded)
        + dim_box(" │")
        + "\n"
        + dim_box("└" + "─" * between + "┘")
    )


def collapse(summary):
    global drawn
    if drawn:
        write("\033[%dA" % drawn)
        for _ in range(drawn):
            write("\033[2K\n")
        write("\033[%dA" % drawn)
        drawn = 0
    if summary:
        color = RED if summary.startswith("Cancelled") else LIGHT_BLUE
        write(boxed_line(summary, color) + "\n")


def read_byte(timeout=None):
    if timeout is not None:
        ready, _, _ = select.select([fd], [], [], timeout)
        if not ready:
            return b""
    return os.read(fd, 1)


def read_key():
    ch = read_byte()
    if not ch:
        return ""
    if ch != b"\x1b":
        return ch.decode("latin1")
    nxt = read_byte(0.25)
    if not nxt:
        return "\x1b"
    if nxt == b"[":
        seq = b"\x1b["
        while True:
            extra = read_byte(0.25)
            if not extra:
                break
            seq += extra
            if extra[0] >= 0x40:
                break
        return seq.decode("latin1")
    if nxt == b"O":
        fin = read_byte(0.25)
        return ("\x1bO" + fin.decode("latin1")) if fin else "\x1bO"
    return "\x1b" + nxt.decode("latin1")


def is_up(key):
    return key == "k" or (key.startswith("\x1b") and key.endswith("A"))


def is_down(key):
    return key == "j" or (key.startswith("\x1b") and key.endswith("B"))


old = termios.tcgetattr(fd)
result = None
summary = None
try:
    write("\033[?25l")
    tty.setcbreak(fd)
    draw()
    while True:
        key = read_key()
        if is_up(key):
            idx = (idx - 1) % len(items)
            draw()
        elif is_down(key):
            idx = (idx + 1) % len(items)
            draw()
        elif key in ("\r", "\n"):
            chosen = items[idx]
            if chosen == "Quit":
                result, summary = "__QUIT__", "Cancelled"
            else:
                result = chosen
                header = title.rstrip(":").strip()
                summary = ("%s : %s" % (header, chosen)) if header else chosen
            break
        elif key in ("q", "Q", "\x03"):
            result, summary = "__QUIT__", "Cancelled"
            break
finally:
    collapse(summary)
    write("\033[?25h")
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    tty_in.close()
    tty_out.close()

if result is None:
    sys.exit(1)
print(result)
PY
}

id_for_label() {
    local client=$1
    local label=$2
    local group=${3:-}
    local ids labels i
    mapfile -t ids < <(cfg cluster-ids "$client" "$group")
    mapfile -t labels < <(cfg cluster-labels "$client" "$group")
    for i in "${!labels[@]}"; do
        if [[ "${labels[$i]}" == "$label" ]]; then
            printf '%s\n' "${ids[$i]}"
            return 0
        fi
    done
    echo "Could not match cluster selection." >&2
    exit 1
}

ensure_kubeconfig() {
    mkdir -p "$(dirname "$KUBECONFIG_PATH")"
    if [[ ! -f "$KUBECONFIG_PATH" ]]; then
        cat > "$KUBECONFIG_PATH" <<'EOF'
apiVersion: v1
kind: Config
clusters: []
contexts: []
current-context: ""
preferences: {}
users: []
EOF
        chmod 600 "$KUBECONFIG_PATH"
    fi
}

set_context_name() {
    local desired=$1
    local current
    current=$(KUBECONFIG="$KUBECONFIG_PATH" oc config current-context 2>/dev/null || true)
    if [[ -z "$current" || "$current" == "$desired" ]]; then
        KUBECONFIG="$KUBECONFIG_PATH" oc config use-context "$desired" >/dev/null 2>&1 || true
        return 0
    fi
    KUBECONFIG="$KUBECONFIG_PATH" oc config delete-context "$desired" >/dev/null 2>&1 || true
    if KUBECONFIG="$KUBECONFIG_PATH" oc config rename-context "$current" "$desired" >/dev/null 2>&1; then
        KUBECONFIG="$KUBECONFIG_PATH" oc config use-context "$desired" >/dev/null 2>&1 || true
    else
        echo "Logged in, but could not rename context to $desired"
    fi
}

pass_file_for() {
    local client=$1
    local explicit=${2:-}
    local p n
    if [[ -n "$explicit" ]]; then
        p=${explicit/#\~/$HOME}
        if [[ -f "$p" ]]; then
            printf '%s\n' "$p"
            return 0
        fi
        return 1
    fi
    for n in "$HOME/.ssh/.${client,,}_pass" "$HOME/.ssh/.${client}_pass"; do
        if [[ -f "$n" ]]; then
            printf '%s\n' "$n"
            return 0
        fi
    done
    return 1
}

print_box() {
    local color=$1
    shift
    python3 "$SCRIPT_DIR/cluster_ui.py" box "$color" "$@"
}

print_vpn_note() {
    python3 "$SCRIPT_DIR/cluster_ui.py" vpn
}

print_login_result() {
    local user server
    echo
    user=$(KUBECONFIG="$KUBECONFIG_PATH" oc whoami 2>/dev/null || KUBECONFIG="$KUBECONFIG_PATH" oc config view --minify -o jsonpath='{..user}' 2>/dev/null || echo unknown)
    server=$(KUBECONFIG="$KUBECONFIG_PATH" oc whoami --show-server 2>/dev/null || echo unknown)
    print_box lightblue "User    : $user" "Server  : $server"
}

login_oc_password() {
    local server=$1 username=$2 insecure=$3 desired=$4 client=$5
    local explicit=${6:-}
    local cmd=(oc login "$server" --username "$username")
    local passfile="" password=""
    if [[ "$insecure" == "true" || "$insecure" == "True" ]]; then
        cmd+=(--insecure-skip-tls-verify)
    fi
    if passfile=$(pass_file_for "$client" "$explicit"); then
        password=$(<"$passfile")
        password=${password%$'\n'}
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "Dry run — would run:"
        echo "  ${cmd[*]}"
        if [[ -n "$passfile" ]]; then
            echo "  password: file $passfile"
        else
            echo "  password: prompt (no ~/.ssh/.${client,,}_pass)"
        fi
        return 0
    fi
    ensure_kubeconfig
    echo
    if [[ -n "$password" ]]; then
        KUBECONFIG="$KUBECONFIG_PATH" "${cmd[@]}" --password "$password"
    else
        echo "No password file for $client. Enter it now, or run: cluster-login set-password $client"
        KUBECONFIG="$KUBECONFIG_PATH" "${cmd[@]}"
    fi
    set_context_name "$desired"
    print_login_result
}

login_kubeconfig() {
    local src=$1 desired=$2 lke_id=${3:-}
    src=${src/#\~/$HOME}
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "Dry run — would use kubeconfig:"
        echo "  $src"
        echo "  exists: $([[ -f "$src" ]] && echo yes || echo no)"
        if [[ -n "$lke_id" && ! -f "$src" ]]; then
            echo "  would fetch LKE kubeconfig for cluster $lke_id"
        fi
        return 0
    fi
    if [[ ! -f "$src" && -n "$lke_id" ]]; then
        if ! command -v linode-cli >/dev/null; then
            echo "Kubeconfig not found: $src" >&2
            echo "Install linode-cli or place the LKE kubeconfig at that path." >&2
            exit 1
        fi
        echo "Fetching LKE kubeconfig..."
        mkdir -p "$(dirname "$src")"
        linode-cli lke cluster-kubeconfig-view "$lke_id" --text | base64 -d > "$src"
        chmod 600 "$src"
    fi
    if [[ ! -f "$src" ]]; then
        echo "Kubeconfig not found: $src" >&2
        echo "This cluster uses an LKE kubeconfig file, not username/password." >&2
        exit 1
    fi
    ensure_kubeconfig
    local src_ctx tmp viewbin
    src_ctx=$(python3 -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1])) or {}; print(d.get("current-context") or "")' "$src")
    tmp=$(mktemp "${KUBECONFIG_PATH}.XXXXXX")
    viewbin=kubectl
    command -v kubectl >/dev/null || viewbin=oc
    KUBECONFIG="$src:$KUBECONFIG_PATH" "$viewbin" config view --flatten --raw > "$tmp"
    chmod 600 "$tmp"
    mv "$tmp" "$KUBECONFIG_PATH"
    local names
    names=$(KUBECONFIG="$KUBECONFIG_PATH" oc config get-contexts -o name)
    if grep -qx "$desired" <<<"$names"; then
        KUBECONFIG="$KUBECONFIG_PATH" oc config use-context "$desired"
    elif [[ -n "$src_ctx" ]] && grep -qx "$src_ctx" <<<"$names"; then
        KUBECONFIG="$KUBECONFIG_PATH" oc config rename-context "$src_ctx" "$desired" >/dev/null 2>&1 || true
        KUBECONFIG="$KUBECONFIG_PATH" oc config use-context "$desired" >/dev/null 2>&1 || true
    fi
    echo "Using kubeconfig $src"
    print_login_result
}

login_from_json() {
    local json=$1
    local client id auth server kubeconfig username insecure desired
    client=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["_client"])' <<<"$json")
    id=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("id") or "")' <<<"$json")
    auth=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("auth") or "")' <<<"$json")
    server=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("server") or "")' <<<"$json")
    kubeconfig=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("kubeconfig") or "")' <<<"$json")
    username=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("_username") or "")' <<<"$json")
    insecure=$(python3 -c 'import json,sys; print(str(json.load(sys.stdin).get("insecure_skip_tls_verify") or "").lower())' <<<"$json")
    passfile=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("_password_file") or "")' <<<"$json")
    lke_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("lke_id") or "")' <<<"$json")
    desired="${client,,}-$id"
    case "$auth" in
        oc-password)
            if [[ -z "$username" || -z "$server" ]]; then
                echo "Catalog entry $id needs username and server for oc-password." >&2
                exit 1
            fi
            login_oc_password "$server" "$username" "$insecure" "$desired" "$client" "$passfile"
            ;;
        kubeconfig)
            if [[ -z "$kubeconfig" ]]; then
                echo "Catalog entry $id needs kubeconfig for kubeconfig auth." >&2
                exit 1
            fi
            login_kubeconfig "$kubeconfig" "$desired" "$lke_id"
            ;;
        *)
            echo "Unsupported auth '$auth' on $id" >&2
            exit 1
            ;;
    esac
}

cmd_status() {
    echo "catalog:    $CONFIG"
    echo "kubeconfig: $KUBECONFIG_PATH"
    if [[ ! -f "$KUBECONFIG_PATH" ]]; then
        echo "context:    (none)"
        echo "whoami:     (none)"
        return 0
    fi
    echo "context:    $(KUBECONFIG="$KUBECONFIG_PATH" oc config current-context 2>/dev/null || echo unset)"
    echo "whoami:     $(KUBECONFIG="$KUBECONFIG_PATH" oc whoami 2>/dev/null || echo not logged in)"
}

resolve_client() {
    python3 - "$CONFIG" "$1" <<'PY'
import sys, yaml
data = yaml.safe_load(open(sys.argv[1])) or {}
name = sys.argv[2]
for key in (data.get("clients") or {}):
    if key.lower() == name.lower():
        print(key)
        raise SystemExit(0)
print("Unknown client %r. Choose: %s" % (name, ", ".join(data.get("clients") or {})), file=sys.stderr)
raise SystemExit(1)
PY
}

cmd_set_password() {
    local client_arg=${1:-} client dest p1 p2
    mapfile -t clients < <(cfg clients)
    if [[ ${#clients[@]} -eq 0 ]]; then
        echo "No clients in $CONFIG" >&2
        exit 1
    fi
    if [[ -n "$client_arg" ]]; then
        client=$(resolve_client "$client_arg")
    else
        client=$(pick "" "${clients[@]}")
        case "$client" in
            __QUIT__) exit 0 ;;
        esac
    fi
    mkdir -p "$HOME/.ssh"
    dest="$HOME/.ssh/.${client,,}_pass"
    read -r -s -p "Password for $client: " p1
    echo
    read -r -s -p "Again: " p2
    echo
    if [[ -z "$p1" ]]; then
        echo "Empty password not saved." >&2
        exit 1
    fi
    if [[ "$p1" != "$p2" ]]; then
        echo "Passwords did not match." >&2
        exit 1
    fi
    umask 077
    printf '%s\n' "$p1" > "$dest"
    chmod 600 "$dest"
    echo "Saved $dest"
}

cmd_login() {
    local client_arg=${1:-} cluster_arg=${2:-}
    local pick_client=1 pick_cluster=1
    [[ -n "$client_arg" ]] && pick_client=0
    [[ -n "$cluster_arg" ]] && pick_cluster=0

    mapfile -t clients < <(cfg clients)
    if [[ ${#clients[@]} -eq 0 ]]; then
        echo "No clients in $CONFIG" >&2
        exit 1
    fi

    print_vpn_note

    local client cluster_id json labels choice group
    if [[ "$pick_client" -eq 0 ]]; then
        client=$(resolve_client "$client_arg")
    else
        client=$(pick "" "${clients[@]}")
        case "$client" in
            __QUIT__) exit 0 ;;
        esac
    fi

    local groups
    mapfile -t groups < <(cfg groups "$client")
    group=""
    if [[ ${#groups[@]} -gt 1 && "$pick_cluster" -eq 1 ]]; then
        group=$(pick "Environment:" "${groups[@]}")
        case "$group" in
            __QUIT__) exit 0 ;;
        esac
    elif [[ ${#groups[@]} -eq 1 ]]; then
        group=${groups[0]}
    fi

    if [[ "$pick_cluster" -eq 0 ]]; then
        cluster_id=$cluster_arg
        json=$(cfg cluster-json "$client" "$cluster_id")
    else
        mapfile -t labels < <(cfg cluster-labels "$client" "$group")
        if [[ ${#labels[@]} -eq 0 ]]; then
            print_box lightblue "No clusters yet"
            exit 0
        fi
        choice=$(pick "Cluster:" "${labels[@]}")
        case "$choice" in
            __QUIT__) exit 0 ;;
        esac
        cluster_id=$(id_for_label "$client" "$choice" "$group")
        json=$(cfg cluster-json "$client" "$cluster_id" "$group")
    fi

    login_from_json "$json"
}

args=()
for a in "$@"; do
    case "$a" in
        -h|--help) usage; exit 0 ;;
        --dry-run) DRY_RUN=1 ;;
        *) args+=("$a") ;;
    esac
done

if [[ ${#args[@]} -gt 0 && "${args[0]}" == "status" ]]; then
    cmd_status
    exit 0
fi

ensure_config

if [[ ${#args[@]} -gt 0 && "${args[0]}" == "list" ]]; then
    cfg list
    exit 0
fi

if [[ ${#args[@]} -gt 0 && "${args[0]}" == "set-password" ]]; then
    cmd_set_password "${args[1]:-}"
    exit 0
fi

cmd_login "${args[0]:-}" "${args[1]:-}"
