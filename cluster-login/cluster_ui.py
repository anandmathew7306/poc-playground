#!/usr/bin/env python3
"""Boxed output and local VPN notes for cluster-login helpers."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RESET = "\033[0m"
DIM = "\033[2m"
MIN_WIDTH = 40
COLORS = {
    "lightblue": "\033[38;5;117m",
    "pink": "\033[38;5;218m",
    "yellow": "\033[1;33m",
    "note": "\033[38;5;250m",
}


def use_color():
    return os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"


def paint(code, text):
    if not use_color():
        return text
    return code + text + RESET


def dim_box(s):
    return paint(DIM, s)


def box_width(lines):
    tw = max(MIN_WIDTH, max((len(x) for x in lines), default=0))
    try:
        cols = os.get_terminal_size().columns
        if cols > 24:
            tw = min(tw, cols - 4)
    except OSError:
        pass
    return tw


def print_box(lines, color="note"):
    if not lines:
        return
    code = COLORS.get(color, COLORS["note"])
    tw = box_width(lines)
    clipped = []
    for line in lines:
        if len(line) > tw:
            line = line[: tw - 1] + "…"
        clipped.append(line.ljust(tw))
    between = tw + 2
    print(dim_box("┌" + "─" * between + "┐"))
    for line in clipped:
        print(dim_box("│ ") + paint(code, line) + dim_box(" │"))
    print(dim_box("└" + "─" * between + "┘"))


def _run(cmd, timeout=3):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _ifaces():
    net = Path("/sys/class/net")
    if not net.is_dir():
        return []
    return [p.name for p in net.iterdir()]


def _proc_running(name):
    try:
        r = subprocess.run(["pgrep", "-x", name], capture_output=True, timeout=2)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def fortinet_state():
    if not shutil.which("forticlient"):
        return "not found"
    r = _run(["forticlient", "vpn", "status"])
    text = ""
    if r is not None:
        text = "%s\n%s" % (r.stdout or "", r.stderr or "")
    low = text.lower()
    match = re.search(r"vpn status:\s*(\w+)", low)
    if match:
        state = match.group(1)
        if state == "connected":
            return "up"
        if state == "connecting":
            return "connecting"
        if state == "disconnected":
            return "down"
    if "disconnected" in low:
        return "down"
    if re.search(r"\bconnected\b", low):
        return "up"
    for name in _ifaces():
        n = name.lower()
        if n.startswith(("fct", "forti", "sslvpn")) or "forti" in n:
            return "up"
    return "down"


def _zerotier_cli(cli, *args):
    r = _run([cli, *args])
    if r is not None and r.returncode == 0:
        return r
    sudo = shutil.which("sudo")
    if sudo:
        r = _run([sudo, "-n", cli, *args])
        if r is not None and r.returncode == 0:
            return r
    return None


def _zerotier_network_rows(stdout):
    rows = []
    for ln in (stdout or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        if low.startswith("nwid") or "<nwid>" in low:
            continue
        rows.append(s)
    return rows


def _zt_iface_up():
    for name in _ifaces():
        if not name.startswith("zt"):
            continue
        oper = Path("/sys/class/net") / name / "operstate"
        try:
            if oper.read_text().strip() == "up":
                return True
        except OSError:
            continue
    return False


def zerotier_state():
    cli = shutil.which("zerotier-cli")
    if not cli and not shutil.which("zerotier-one"):
        return "not found"
    if cli:
        nets = _zerotier_cli(cli, "listnetworks")
        if nets is not None:
            rows = _zerotier_network_rows(nets.stdout)
            if any(re.search(r"\bOK\b", ln) for ln in rows):
                return "up"
            # Queried successfully: leave/stop leaves the daemon and a DOWN zt*
            # iface behind. That is not VPN-up.
            return "down"
        info = _zerotier_cli(cli, "status") or _zerotier_cli(cli, "info")
        if info is not None:
            out = info.stdout or ""
            if "OFFLINE" in out:
                return "down"
            if "ONLINE" in out:
                # Daemon is up; still need a joined network to count as VPN.
                pass
    if _zt_iface_up():
        return "up"
    if _proc_running("zerotier-one"):
        return "down"
    return "down"


def vpn_lines():
    return [
        "Fortinet : %s" % fortinet_state(),
        "ZeroTier : %s" % zerotier_state(),
    ]


def print_vpn_box():
    print_box(vpn_lines(), "note")


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print("Usage: cluster_ui.py box COLOR LINE... | vpn", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "vpn":
        print_vpn_box()
        return 0
    if cmd == "box":
        color = argv[2] if len(argv) > 2 else "note"
        print_box(argv[3:], color)
        return 0
    print("unknown command %r" % cmd, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
