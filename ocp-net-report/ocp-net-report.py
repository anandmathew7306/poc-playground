#!/usr/bin/env python3
"""
ocp-net-report.py — generate a full network reference report for an
OpenShift cluster: core networking + MetalLB.

For scoped reports use the sibling scripts: ocp-net-core-report
(host/node networking only) or ocp-net-metallb-report (MetalLB only).

Read-only. Runs `oc get ... -o json` and prints markdown tables.
Requires: python3 + oc (logged in). No pip packages.

Usage:
    python3 ocp-net-report.py                 # print to stdout
    python3 ocp-net-report.py --all-nics      # include down/unused NICs and geneve device
    python3 ocp-net-report.py > report.md     # save to file
"""

import argparse
import ipaddress
import json
import re
import subprocess
import sys
from datetime import datetime

SHOW_ALL_NICS = False

# short_node -> 0 for control-plane/master, 1 otherwise; populated in main()
_NODE_ROLE_RANK = {}


def _natural_key(name):
    """Split trailing/embedded digits so compute2 sorts before compute10."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def _node_key(name):
    """Sort key: control-plane nodes first, then natural (numeric) hostname."""
    short = name.split(".", 1)[0]
    return (_NODE_ROLE_RANK.get(short, 1), _natural_key(short))


def oc_json(args):
    """Run `oc <args> -o json` and return parsed JSON (or None on failure)."""
    cmd = ["oc"] + args + ["-o", "json"]
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True,
                             check=True)
        return json.loads(out.stdout)
    except subprocess.CalledProcessError as e:
        print(f"  > command failed: {' '.join(cmd)}", file=sys.stderr)
        print(f"  > {e.stderr.strip()}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"  > could not parse JSON: {' '.join(cmd)}", file=sys.stderr)
        return None


def oc_text(args):
    """Run `oc <args>` and return stripped stdout ('' on failure)."""
    try:
        return subprocess.run(["oc"] + args, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              universal_newlines=True).stdout.strip()
    except Exception:
        return ""


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


def default_routes(state):
    """Map route-table-id -> (gateway, iface) from default routes (IPv4 preferred)."""
    gw_by_table = {}
    for r in state.get("routes", {}).get("config", []):
        if r.get("destination") in ("0.0.0.0/0", "::/0"):
            tid = r.get("table-id")
            existing = gw_by_table.get(tid)
            is_v4 = r.get("destination") == "0.0.0.0/0"
            if existing is None or is_v4:
                gw_by_table[tid] = (r.get("next-hop-address", "-"),
                                    r.get("next-hop-interface", "-"))
    return gw_by_table


def first_state(nns):
    """State of the first node (alphabetical) — used for cluster-identical data."""
    return next(iter(sorted(nns.items(), key=lambda kv: _node_key(kv[0]))),
                (None, {}))[1]


# ---------- Cluster Overview ----------
def cluster_overview(nodes):
    rows = []
    infra = oc_json(["get", "infrastructure", "cluster"])
    if infra:
        st = infra.get("status", {})
        rows.append(["Cluster", st.get("infrastructureName", "-")])
        rows.append(["Platform", st.get("platformStatus", {}).get("type", "-")])
        rows.append(["API URL", st.get("apiServerURL", "-")])
        bm = st.get("platformStatus", {}).get("baremetal", {}) or {}
        if bm:
            rows.append(["API VIP(s)",
                         ", ".join(bm.get("apiServerInternalIPs", []) or []) or "-"])
            rows.append(["Ingress VIP(s)",
                         ", ".join(bm.get("ingressIPs", []) or []) or "-"])
    console = oc_text(["whoami", "--show-console"])
    if console:
        rows.append(["Console", console])
    cv = oc_json(["get", "clusterversion", "version"])
    if cv:
        rows.append(["OpenShift version",
                     cv.get("status", {}).get("desired", {}).get("version", "-")])
    net = oc_json(["get", "network.config.openshift.io", "cluster"])
    if net:
        st = net.get("status", {}) or net.get("spec", {})
        rows.append(["CNI", st.get("networkType", "-")])
        pods = ", ".join(f"{c.get('cidr')} (hostPrefix /{c.get('hostPrefix')})"
                         for c in st.get("clusterNetwork", []) or [])
        rows.append(["Pod network", pods or "-"])
        rows.append(["Service network",
                     ", ".join(st.get("serviceNetwork", []) or []) or "-"])
    ing = oc_json(["get", "ingresses.config.openshift.io", "cluster"])
    if ing:
        rows.append(["Apps domain", ing.get("spec", {}).get("domain", "-")])
    cp = 0
    for n in nodes:
        labels = n.get("metadata", {}).get("labels", {})
        if ("node-role.kubernetes.io/control-plane" in labels
                or "node-role.kubernetes.io/master" in labels):
            cp += 1
    workers = len(nodes) - cp
    topo = f"{len(nodes)} nodes — {cp} control-plane"
    topo += f", {workers} dedicated workers" if workers else " (compact, no dedicated workers)"
    rows.append(["Topology", topo])
    return "## Cluster Overview\n\n" + md_table(["Item", "Value"], rows)


# ---------- Node Inventory ----------
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
    rows.sort(key=lambda r: _node_key(r[0]))
    return "## Node Inventory\n\n" + md_table(["Hostname", "Role", "IPv4", "IPv6"], rows)


# ---------- Physical NIC Inventory ----------
def nic_inventory(nns):
    rows = []
    for node, state in sorted(nns.items(), key=lambda kv: _node_key(kv[0])):
        for i in ifaces_of(state):
            if i.get("type") != "ethernet":
                continue
            name = i.get("name", "")
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


# ---------- Bond Detail ----------
def bond_inventory(nns):
    rows = []
    for node, state in sorted(nns.items(), key=lambda kv: _node_key(kv[0])):
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


# ---------- OVS Bridges ----------
def ovs_overview(nns):
    state = first_state(nns)
    brows = []
    for i in ifaces_of(state):
        if i.get("type") != "ovs-bridge":
            continue
        name = i.get("name", "")
        ports = sorted(p.get("name", "")
                       for p in i.get("bridge", {}).get("port", []) or []
                       if p.get("name") != name
                       and not p.get("name", "").startswith("patch-"))
        brows.append([name, ", ".join(ports) or "-"])
    brows.sort(key=lambda r: r[0])

    # OVN localnet patch ports reveal which VLANs VMs attach to directly
    localnets = set()
    for i in ifaces_of(state):
        if i.get("type") != "ovs-bridge":
            continue
        for p in i.get("bridge", {}).get("port", []) or []:
            pname = p.get("name", "")
            if pname.startswith("patch-") and "_ovn_localnet_port" in pname:
                localnets.add(pname[len("patch-"):pname.index("_ovn_localnet_port")])

    irows = []
    for node, st in sorted(nns.items(), key=lambda kv: _node_key(kv[0])):
        for i in ifaces_of(st):
            if i.get("type") != "ovs-interface":
                continue
            v4 = fmt_addresses(i.get("ipv4"))
            v6 = fmt_addresses(i.get("ipv6"))
            if v4 == "-" and v6 == "-":
                continue
            irows.append([short_node(node), i.get("name", ""), v4, v6])

    out = ("## OVS Bridges\n\n"
           "_Bridge layout is identical across nodes; shown once "
           "(internal and OVN patch ports omitted). "
           "`br-ex` carries the node/machine IP; `ovs0` hands workload VLANs to the host stack._\n\n"
           + md_table(["Bridge", "Ports"], brows))
    if localnets:
        out += ("\n**OVN localnet networks** (direct VM attachment via br-int patch ports): "
                + ", ".join(f"`{n}`" for n in sorted(localnets)) + "\n")
    if irows:
        out += "\n**Host IPs on OVS interfaces:**\n\n" + md_table(
            ["Node", "Interface", "IPv4", "IPv6"], irows)
    return out


# ---------- Network Map (consolidated, one row per VLAN) ----------
def network_map(nns):
    state = first_state(nns)
    ifaces = ifaces_of(state)
    gw_by_table = default_routes(state)

    vrf_of = {}        # member iface name -> vrf name
    table_of_vrf = {}  # vrf name -> route-table-id
    for i in ifaces:
        if i.get("type") != "vrf":
            continue
        v = i.get("vrf", {})
        for p in v.get("port", []) or []:
            vrf_of[p] = i.get("name", "")
        table_of_vrf[i.get("name", "")] = v.get("route-table-id")

    bridge_of_port = {}  # iface name -> ovs bridge it is a port of
    for i in ifaces:
        if i.get("type") != "ovs-bridge":
            continue
        for p in i.get("bridge", {}).get("port", []) or []:
            bridge_of_port[p.get("name", "")] = i.get("name", "")

    agg = {}
    for _, st in sorted(nns.items(), key=lambda kv: _node_key(kv[0])):
        for i in ifaces_of(st):
            if i.get("type") != "vlan":
                continue
            vid = i.get("vlan", {}).get("id")
            e = agg.setdefault(vid, {"names": set(), "parents": set(),
                                     "v4": set(), "v6": set()})
            e["names"].add(i.get("name", ""))
            e["parents"].add(i.get("vlan", {}).get("base-iface", "-"))
            for fam, key in (("ipv4", "v4"), ("ipv6", "v6")):
                blk = i.get(fam) or {}
                if not blk.get("enabled"):
                    continue
                for a in blk.get("address", []) or []:
                    ip, plen = a.get("ip"), a.get("prefix-length")
                    if ip is None or plen is None or ip.startswith("fe80:"):
                        continue
                    # skip /32 & /128 secondaries (MetalLB service IPs)
                    if (":" not in ip and plen == 32) or (":" in ip and plen == 128):
                        continue
                    try:
                        e[key].add(str(ipaddress.ip_interface(f"{ip}/{plen}").network))
                    except ValueError:
                        pass

    rows = []
    for vid in sorted(agg, key=lambda x: int(x)):
        e = agg[vid]
        vrf = next((vrf_of[n] for n in sorted(e["names"]) if n in vrf_of), None)
        gw = "-"
        if vrf:
            gw = gw_by_table.get(table_of_vrf.get(vrf), ("-", "-"))[0]
        kind = "routed (VRF)" if vrf else "L2-only"
        br = next((bridge_of_port[n] for n in sorted(e["names"])
                   if n in bridge_of_port), None)
        if br:
            kind = f"uplink of {br}"
            if br == "br-ex":
                vrf = "main"
                gw = gw_by_table.get(254, ("-", "-"))[0]
        rows.append([vid,
                     ", ".join(sorted(e["parents"])),
                     ", ".join(sorted(e["v4"])) or "-",
                     ", ".join(sorted(e["v6"])) or "-",
                     vrf or "-", gw, kind])
    return ("## Network Map\n\n"
            "_One row per VLAN, aggregated across nodes. /32 & /128 secondaries "
            "(MetalLB service IPs) are excluded from subnet derivation._\n\n"
            + md_table(["VLAN", "Parent", "IPv4 Subnet", "IPv6 Subnet",
                        "VRF", "Gateway", "Type"], rows))


# ---------- VLAN & Interface Detail (per node) ----------
def vlan_inventory(nns):
    rows = []
    for node, state in sorted(nns.items(), key=lambda kv: _node_key(kv[0])):
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
    return "## VLAN & Interface Detail (per node)\n\n" + md_table(
        ["Node", "Interface", "VLAN", "Parent", "IPv4", "IPv6", "MTU"], rows)


# ---------- VRF & Routing ----------
def vrf_inventory(nns):
    """One row per VRF (taken from the first node; VRFs are identical across nodes)."""
    state = first_state(nns)
    gw_by_table = default_routes(state)

    rows = []
    for i in ifaces_of(state):
        if i.get("type") != "vrf":
            continue
        v = i.get("vrf", {})
        tid = v.get("route-table-id", "-")
        ports = ", ".join(v.get("port", []))
        gw, _ = gw_by_table.get(tid, ("-", "-"))
        rows.append([i.get("name", ""), tid, ports, gw])

    gw254, if254 = gw_by_table.get(254, ("-", "-"))
    rows.append(["main", 254, if254, gw254])
    rows.sort(key=lambda r: str(r[0]))
    return ("## VRF & Routing\n\n"
            "_VRFs are identical across nodes; shown once. Gateway = IPv4 default route for that table._\n\n"
            + md_table(["VRF", "Table ID", "Interface(s)", "Default Gateway"], rows))


# ---------- BGP Peers ----------
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
    return ("## BGP Peers\n\n"
            "_Also documents the cluster's L3 adjacency to the upstream "
            "a/b routers per VRF._\n\n"
            + md_table(["Name", "Peer Address", "myASN", "peerASN", "VRF", "BFD"], rows))


# ---------- IP Address Pools ----------
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


# ---------- BGP Advertisements ----------
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


# ---------- LoadBalancer Services ----------
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
    global SHOW_ALL_NICS
    p = argparse.ArgumentParser(
        description="Generate a markdown network reference report "
                    "(core networking + MetalLB) for an OpenShift cluster (read-only).")
    p.add_argument("--all-nics", action="store_true",
                   help="include down/unused NICs and the geneve device")
    args = p.parse_args()
    SHOW_ALL_NICS = args.all_nics

    print("# OpenShift Network Reference\n")
    server = oc_text(["whoami", "--show-server"])
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print(f"_Server:_ `{server}`  ·  _Generated:_ {stamp}\n")
    print("> Point-in-time snapshot of live cluster state. Values drift — "
          "regenerate before relying on specifics.\n")

    nodes = get_nodes()
    nns = get_nns_all()
    if not nodes or not nns:
        sys.exit("error: could not fetch nodes/nns from the cluster — "
                 "check connectivity and login; no report written")
    for n in nodes:
        labels = n.get("metadata", {}).get("labels", {})
        is_cp = ("node-role.kubernetes.io/control-plane" in labels
                 or "node-role.kubernetes.io/master" in labels)
        _NODE_ROLE_RANK[short_node(n.get("metadata", {}).get("name", ""))] = \
            0 if is_cp else 1
    print(cluster_overview(nodes))
    print(node_inventory(nodes))
    print(nic_inventory(nns))
    print(bond_inventory(nns))
    print(ovs_overview(nns))
    print(network_map(nns))
    print(vlan_inventory(nns))
    print(vrf_inventory(nns))
    print(bgp_peers())
    print(ip_pools())
    print(bgp_advertisements())
    print(lb_services())


if __name__ == "__main__":
    main()
