#!/usr/bin/env python3
"""
ocp-net-report.py — generate a network reference report for an OpenShift cluster.

Read-only. Runs `oc get ... -o json` and prints markdown tables.
Requires: python3 + oc (logged in). No pip packages.

Usage:
    python3 ocp-net-report.py                 # print to stdout
    python3 ocp-net-report.py > report.md     # save to file
    python3 ocp-net-report.py --all-nics      # include down/unused NICs and geneve device
"""

import json
import subprocess
import sys

SHOW_ALL_NICS = "--all-nics" in sys.argv


def oc_json(args):
    """Run `oc <args> -o json` and return parsed JSON (or None on failure)."""
    cmd = ["oc"] + args + ["-o", "json"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(out.stdout)
    except subprocess.CalledProcessError as e:
        print(f"  > command failed: {' '.join(cmd)}", file=sys.stderr)
        print(f"  > {e.stderr.strip()}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"  > could not parse JSON: {' '.join(cmd)}", file=sys.stderr)
        return None


def md_table(headers, rows):
    if not rows:
        return "_no data_\n"
    h = "| " + " | ".join(headers) + " |"
    s = "|" + "|".join(["---"] * len(headers)) + "|"
    r = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([h, s] + r) + "\n"


def short_node(name):
    return name.split(".", 1)[0]


def fmt_addresses(ipblock):
    if not ipblock or not ipblock.get("enabled"):
        return "-"
    addrs = ipblock.get("address", []) or []
    parts = [f"{a.get('ip')}/{a.get('prefix-length')}" for a in addrs]
    return ", ".join(parts) if parts else "-"


# ---------- data fetch ----------
def get_nodes():
    d = oc_json(["get", "nodes"])
    return d.get("items", []) if d else []


def get_nns_all():
    """Return {node: full currentState dict} for every node."""
    d = oc_json(["get", "nns"])
    out = {}
    if not d:
        return out
    for item in d.get("items", []):
        name = item.get("metadata", {}).get("name", "")
        out[name] = item.get("status", {}).get("currentState", {})
    return out


def ifaces_of(state):
    return state.get("interfaces", [])


# ---------- Table 1: Node Inventory ----------
def node_inventory(nodes):
    rows = []
    for item in nodes:
        meta = item.get("metadata", {})
        name = meta.get("name", "")
        roles = sorted(
            l.split("/", 1)[1]
            for l in meta.get("labels", {})
            if l.startswith("node-role.kubernetes.io/")
        )
        ipv4 = ipv6 = "-"
        for a in item.get("status", {}).get("addresses", []):
            if a.get("type") == "InternalIP":
                ip = a.get("address", "")
                ipv6 = ip if ":" in ip else ipv6
                ipv4 = ip if ":" not in ip else ipv4
        rows.append([name, ",".join(roles) or "-", ipv4, ipv6])
    rows.sort(key=lambda r: r[0])
    return "## Node Inventory\n\n" + md_table(["Hostname", "Role", "IPv4", "IPv6"], rows)


# ---------- Table 2: Physical NIC Inventory ----------
def nic_inventory(nns):
    rows = []
    for node, state in sorted(nns.items()):
        for i in ifaces_of(state):
            if i.get("type") != "ethernet":
                continue
            name = i.get("name", "")
            # filter noise unless --all-nics
            if not SHOW_ALL_NICS:
                if name.startswith("genev_sys"):
                    continue
                if i.get("state") != "up":
                    continue
            rows.append([
                short_node(node), name,
                (i.get("mac-address") or "-").lower(),
                i.get("controller") or "-",
                i.get("mtu", "-"), i.get("state", "-"),
            ])
    note = "" if SHOW_ALL_NICS else "_(up interfaces only; run with `--all-nics` to see all)_\n\n"
    return "## Physical NIC Inventory\n\n" + note + md_table(
        ["Node", "Interface", "MAC", "Controller", "MTU", "State"], rows)


# ---------- Table 3: Bond Detail ----------
def bond_inventory(nns):
    rows = []
    for node, state in sorted(nns.items()):
        for i in ifaces_of(state):
            if i.get("type") != "bond":
                continue
            la = i.get("link-aggregation", {})
            o = la.get("options", {})
            rows.append([
                short_node(node), i.get("name", ""),
                la.get("mode", "-"), o.get("lacp_rate", "-"),
                o.get("miimon", "-"), i.get("mtu", "-"),
                ", ".join(la.get("port", [])),
            ])
    return "## Bond Detail\n\n" + md_table(
        ["Node", "Bond", "Mode", "lacp_rate", "miimon", "MTU", "Members"], rows)


# ---------- Table 4: VLAN & Interface Summary ----------
def vlan_inventory(nns):
    rows = []
    for node, state in sorted(nns.items()):
        for i in ifaces_of(state):
            if i.get("type") != "vlan":
                continue
            v = i.get("vlan", {})
            rows.append([
                short_node(node), i.get("name", ""), v.get("id", "-"),
                v.get("base-iface", "-"),
                fmt_addresses(i.get("ipv4")), fmt_addresses(i.get("ipv6")),
                i.get("mtu", "-"),
            ])
    return "## VLAN & Interface Summary\n\n" + md_table(
        ["Node", "Interface", "VLAN", "Parent", "IPv4", "IPv6", "MTU"], rows)


# ---------- Table 5: VRF & Routing ----------
def vrf_inventory(nns):
    """One row per VRF (taken from the first node; VRFs are identical across nodes)."""
    # pick any node's state
    state = next(iter(nns.values()), {})
    ifaces = ifaces_of(state)
    routes = state.get("routes", {}).get("config", [])

    # map table-id -> (gateway, iface) from default routes
    gw_by_table = {}
    for r in routes:
        if r.get("destination") in ("0.0.0.0/0", "::/0"):
            tid = r.get("table-id")
            # prefer IPv4 default; only set if not already an IPv4 entry
            existing = gw_by_table.get(tid)
            is_v4 = r.get("destination") == "0.0.0.0/0"
            if existing is None or is_v4:
                gw_by_table[tid] = (r.get("next-hop-address", "-"),
                                    r.get("next-hop-interface", "-"))

    rows = []
    for i in ifaces:
        if i.get("type") != "vrf":
            continue
        v = i.get("vrf", {})
        tid = v.get("route-table-id", "-")
        ports = ", ".join(v.get("port", []))
        gw, _ = gw_by_table.get(tid, ("-", "-"))
        rows.append([i.get("name", ""), tid, ports, gw])

    # main table (254) for reference
    gw254, if254 = gw_by_table.get(254, ("-", "-"))
    rows.append(["main", 254, if254, gw254])
    rows.sort(key=lambda r: str(r[0]))
    return ("## VRF & Routing\n\n"
            "_VRFs are identical across nodes; shown once. Gateway = IPv4 default route for that table._\n\n"
            + md_table(["VRF", "Table ID", "Interface(s)", "Default Gateway"], rows))


# ---------- Table 6: BGP Peers ----------
def bgp_peers():
    d = oc_json(["get", "bgppeers", "-n", "metallb-system"])
    if not d:
        return "## BGP Peers\n\n_could not retrieve (metallb-system)_\n"
    rows = []
    for item in d.get("items", []):
        spec = item.get("spec", {})
        rows.append([
            item.get("metadata", {}).get("name", ""),
            spec.get("peerAddress", "-"),
            spec.get("myASN", "-"),
            spec.get("peerASN", "-"),
            spec.get("vrf", "-") or "main",
            (spec.get("bfdProfile") or "-"),
        ])
    rows.sort(key=lambda r: r[0])
    return "## BGP Peers\n\n" + md_table(
        ["Name", "Peer Address", "myASN", "peerASN", "VRF", "BFD"], rows)


# ---------- Table 7: IP Address Pools ----------
def ip_pools():
    d = oc_json(["get", "ipaddresspools", "-n", "metallb-system"])
    if not d:
        return "## IP Address Pools\n\n_could not retrieve (metallb-system)_\n"
    rows = []
    for item in d.get("items", []):
        spec = item.get("spec", {})
        rows.append([
            item.get("metadata", {}).get("name", ""),
            ", ".join(spec.get("addresses", [])),
            str(spec.get("autoAssign", "-")).lower(),
            str(spec.get("avoidBuggyIPs", "-")).lower(),
        ])
    rows.sort(key=lambda r: r[0])
    return "## IP Address Pools\n\n" + md_table(
        ["Name", "Addresses", "autoAssign", "avoidBuggyIPs"], rows)


# ---------- Table 7b: BGP Advertisements ----------
def bgp_advertisements():
    d = oc_json(["get", "bgpadvertisements", "-n", "metallb-system"])
    if not d:
        return "## BGP Advertisements\n\n_could not retrieve (metallb-system)_\n"
    rows = []
    for item in d.get("items", []):
        spec = item.get("spec", {})
        rows.append([
            item.get("metadata", {}).get("name", ""),
            ", ".join(spec.get("ipAddressPools", []) or []) or "(all)",
            ", ".join(spec.get("peers", []) or []) or "(all)",
            spec.get("aggregationLength", "-"),
            spec.get("localPref", "-"),
        ])
    rows.sort(key=lambda r: r[0])
    return "## BGP Advertisements\n\n" + md_table(
        ["Name", "Pools", "Peers", "AggLen", "localPref"], rows)


# ---------- Table 8: LoadBalancer Services ----------
def lb_services():
    d = oc_json(["get", "svc", "-A", "--field-selector", "spec.type=LoadBalancer"])
    if not d:
        return "## LoadBalancer Services\n\n_could not retrieve_\n"
    rows = []
    for item in d.get("items", []):
        meta = item.get("metadata", {})
        status = item.get("status", {}).get("loadBalancer", {}).get("ingress", [])
        ext = ", ".join(i.get("ip", "") for i in status) if status else "<pending>"
        rows.append([
            meta.get("namespace", ""), meta.get("name", ""), ext,
        ])
    rows.sort(key=lambda r: (r[0], r[1]))
    return "## LoadBalancer Services\n\n" + md_table(
        ["Namespace", "Service", "External IP"], rows)


# ---------- main ----------
def main():
    print("# OpenShift Network Reference\n")
    try:
        who = subprocess.run(["oc", "whoami"], capture_output=True, text=True).stdout.strip()
        ctx = subprocess.run(["oc", "whoami", "--show-server"],
                             capture_output=True, text=True).stdout.strip()
        print(f"_Server:_ `{ctx}`  ·  _User:_ `{who}`\n")
    except Exception:
        pass

    nodes = get_nodes()
    nns = get_nns_all()

    print(node_inventory(nodes))
    print(nic_inventory(nns))
    print(bond_inventory(nns))
    print(vlan_inventory(nns))
    print(vrf_inventory(nns))
    print(bgp_peers())
    print(ip_pools())
    print(bgp_advertisements())
    print(lb_services())


if __name__ == "__main__":
    main()