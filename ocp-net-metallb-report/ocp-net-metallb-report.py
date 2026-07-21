#!/usr/bin/env python3
"""
ocp-net-metallb-report.py — generate a MetalLB reference report for an
OpenShift cluster.

Covers MetalLB / load-balancer networking: operator CR, BFD profiles,
BGP peers, IP address pools, BGP/L2 advertisements, LoadBalancer services,
EgressService (LB-tied egress), plus FRR/BGP status summaries.

Host/node underlay: sibling ocp-net-core-report.
OVN EgressIP, Multus, etc.: Extended Networking (separate report; not here).
Combined core+MetalLB: ocp-net-report.

Read-only. Runs `oc get ... -o json` and prints markdown tables.
Requires: python3 + oc (logged in). No pip packages.

Usage:
    python3 ocp-net-metallb-report.py                 # print to stdout
    python3 ocp-net-metallb-report.py > report.md     # save to file
"""

import json
import subprocess
import sys
from collections import Counter
from datetime import datetime


POOL_ANN_KEYS = (
    "metallb.io/address-pool",
    "metallb.universe.tf/address-pool",
)
IP_ANN_KEYS = (
    "metallb.io/loadBalancerIPs",
    "metallb.universe.tf/loadBalancerIPs",
)


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


def fmt_node_selectors(selectors):
    """Compact MetalLB/OVN nodeSelector list → readable string."""
    if not selectors:
        return "(none)"
    parts = []
    for sel in selectors:
        ml = sel.get("matchLabels") or {}
        if ml:
            parts.append(",".join(f"{k}={v}" for k, v in sorted(ml.items())))
        for expr in sel.get("matchExpressions") or []:
            key = expr.get("key", "?")
            op = expr.get("operator", "?")
            vals = ",".join(expr.get("values") or [])
            parts.append(f"{key} {op} [{vals}]" if vals else f"{key} {op}")
    return "; ".join(parts) if parts else "(none)"


def fmt_ports(spec):
    ports = spec.get("ports") or []
    if not ports:
        return "-"
    bits = []
    for p in ports:
        name = p.get("name") or ""
        port = p.get("port", "?")
        proto = p.get("protocol", "TCP")
        bits.append(f"{name}:{port}/{proto}" if name else f"{port}/{proto}")
    return ", ".join(bits)


def ann_first(meta, keys):
    anns = meta.get("annotations") or {}
    for k in keys:
        if k in anns and anns[k]:
            return anns[k]
    return "-"


# ---------- MetalLB operator CR ----------
def metallb_cr():
    d = oc_json(["get", "metallbs", "-n", "metallb-system"])
    if not d:
        return "## MetalLB Operator\n\n_could not retrieve (metallb-system)_\n"
    items = d.get("items", [])
    if not items:
        return "## MetalLB Operator\n\n_no MetalLB CRs_\n"
    rows = []
    for item in items:
        meta = item.get("metadata", {})
        spec = item.get("spec", {}) or {}
        status = item.get("status", {}) or {}
        log_level = spec.get("logLevel") or "-"
        sc = spec.get("speakerConfig") or {}
        raw_ns = sc.get("nodeSelector") or spec.get("nodeSelector") or {}
        if isinstance(raw_ns, dict) and raw_ns:
            node_sel = ",".join(f"{k}={v}" for k, v in sorted(raw_ns.items()))
        else:
            node_sel = "(none)"
        conds = status.get("conditions") or []
        avail = next(
            (c.get("status") for c in conds if c.get("type") == "Available"),
            "-")
        rows.append([
            meta.get("name", ""),
            meta.get("namespace", ""),
            log_level,
            node_sel,
            avail,
        ])
    rows.sort(key=lambda r: (r[1], r[0]))
    return ("## MetalLB Operator\n\n"
            "_Cluster MetalLB CR(s) — speaker placement / log level._\n\n"
            + md_table(["Name", "Namespace", "logLevel", "speaker nodeSelector",
                        "Available"], rows))


# ---------- BFD Profiles ----------
def bfd_profiles():
    d = oc_json(["get", "bfdprofiles", "-n", "metallb-system"])
    if not d:
        return "## BFD Profiles\n\n_could not retrieve (metallb-system)_\n"
    rows = []
    for item in d.get("items", []):
        spec = item.get("spec", {}) or {}
        rows.append([
            item.get("metadata", {}).get("name", ""),
            spec.get("detectMultiplier", "-"),
            spec.get("receiveInterval", "-"),
            spec.get("transmitInterval", "-"),
            spec.get("echoInterval", "-"),
            str(spec.get("echoMode", "-")).lower()
            if spec.get("echoMode") is not None else "-",
            str(spec.get("passiveMode", "-")).lower()
            if spec.get("passiveMode") is not None else "-",
        ])
    rows.sort(key=lambda r: r[0])
    return ("## BFD Profiles\n\n"
            + md_table(["Name", "detectMult", "rx(ms)", "tx(ms)", "echo(ms)",
                        "echoMode", "passive"], rows))


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
            fmt_node_selectors(spec.get("nodeSelectors") or []),
        ])
    rows.sort(key=lambda r: r[0])
    return ("## BGP Peers\n\n"
            "_Also documents the cluster's L3 adjacency to the upstream "
            "a/b routers per VRF._\n\n"
            + md_table(["Name", "Peer Address", "myASN", "peerASN", "VRF",
                        "BFD", "nodeSelectors"], rows))


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
            fmt_node_selectors(spec.get("nodeSelectors") or []),
        ])
    rows.sort(key=lambda r: r[0])
    return ("## BGP Advertisements\n\n"
            "_`nodeSelectors` restrict which nodes may advertise — wrong "
            "labels are a common cause of 'IP assigned but unreachable'._\n\n"
            + md_table(["Name", "Pools", "Peers", "AggLen", "localPref",
                        "nodeSelectors"], rows))


# ---------- L2 Advertisements ----------
def l2_advertisements():
    d = oc_json(["get", "l2advertisements", "-n", "metallb-system"])
    if not d:
        return "## L2 Advertisements\n\n_could not retrieve (metallb-system)_\n"
    rows = []
    for item in d.get("items", []):
        spec = item.get("spec", {}) or {}
        ifaces = ", ".join(spec.get("interfaces") or []) or "(all)"
        rows.append([
            item.get("metadata", {}).get("name", ""),
            ", ".join(spec.get("ipAddressPools") or []) or "(all)",
            ifaces,
            fmt_node_selectors(spec.get("nodeSelectors") or []),
        ])
    rows.sort(key=lambda r: r[0])
    return ("## L2 Advertisements\n\n"
            "_ARP/NDP advertisement path (may be empty on BGP-only "
            "clusters)._\n\n"
            + md_table(["Name", "Pools", "Interfaces", "nodeSelectors"], rows))


# ---------- LoadBalancer Services ----------
def lb_services():
    d = oc_json(["get", "svc", "-A", "--field-selector", "spec.type=LoadBalancer"])
    if not d:
        return "## LoadBalancer Services\n\n_could not retrieve_\n"
    rows = []
    pending = 0
    for item in d.get("items", []):
        meta = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {}).get("loadBalancer", {}).get("ingress", [])
        ext = ", ".join(i.get("ip", "") for i in status) if status else "<pending>"
        if ext == "<pending>":
            pending += 1
        rows.append([
            meta.get("namespace", ""),
            meta.get("name", ""),
            ext,
            ann_first(meta, POOL_ANN_KEYS),
            ann_first(meta, IP_ANN_KEYS),
            spec.get("externalTrafficPolicy", "-"),
            fmt_ports(spec),
        ])
    rows.sort(key=lambda r: (r[0], r[1]))
    note = (f"_Total: {len(rows)} · pending (no external IP): {pending}. "
            f"Pending rows are often noise (lab leftovers); confirm before "
            f"documenting as active._\n\n")
    return ("## LoadBalancer Services\n\n" + note
            + md_table(["Namespace", "Service", "External IP", "pool ann",
                        "LB IP ann", "extTrafficPolicy", "Ports"], rows))


# ---------- EgressService (LB-tied; not EgressIP) ----------
def egress_services():
    d = oc_json(["get", "egressservices", "-A"])
    if not d:
        return ("## EgressServices\n\n"
                "_could not retrieve (k8s.ovn.org) — CRD missing or "
                "no access_\n")
    rows = []
    for item in d.get("items", []):
        meta = item.get("metadata", {})
        spec = item.get("spec", {}) or {}
        status = item.get("status", {}) or {}
        # nodeSelector on EgressService is a LabelSelector (matchLabels map)
        ns = spec.get("nodeSelector") or {}
        if isinstance(ns, dict) and ("matchLabels" in ns or "matchExpressions" in ns):
            ns_s = fmt_node_selectors([ns])
        elif isinstance(ns, dict) and ns:
            ns_s = ",".join(f"{k}={v}" for k, v in sorted(ns.items()))
        else:
            ns_s = "(none)"
        rows.append([
            meta.get("namespace", ""),
            meta.get("name", ""),
            spec.get("sourceIPBy", "-"),
            status.get("host") or status.get("node") or "-",
            ns_s,
        ])
    rows.sort(key=lambda r: (r[0], r[1]))
    return ("## EgressServices\n\n"
            "_OVN EgressService tied to a LoadBalancer Service "
            "(`sourceIPBy: LoadBalancerIP` = symmetric in/out on the LB IP). "
            "**Not** OVN EgressIP — that belongs under Extended Networking._\n\n"
            + md_table(["Namespace", "Name", "sourceIPBy", "status host",
                        "nodeSelector"], rows))


# ---------- Status summaries (avoid dumping dozens of rows) ----------
def service_bgp_status_summary():
    d = oc_json(["get", "servicebgpstatuses", "-A"])
    if not d:
        return ("## ServiceBGPStatus (summary)\n\n"
                "_could not retrieve_\n")
    items = d.get("items", [])
    by_ns = Counter()
    with_peers = 0
    for item in items:
        meta = item.get("metadata", {})
        by_ns[meta.get("namespace", "?")] += 1
        status = item.get("status", {}) or {}
        peers = status.get("peers") or status.get("nodePeers") or []
        if peers:
            with_peers += 1
    top = by_ns.most_common(10)
    rows = [[ns, str(n)] for ns, n in top]
    return ("## ServiceBGPStatus (summary)\n\n"
            f"_Noise control: {len(items)} objects total; "
            f"{with_peers} report peer info. Top namespaces by count "
            f"(not a full dump)._\n\n"
            + md_table(["Namespace", "Count"], rows))


def bgp_session_state_summary():
    d = oc_json(["get", "bgpsessionstates", "-A"])
    if not d:
        return ("## BGPSessionState (summary)\n\n"
                "_could not retrieve (frrk8s.metallb.io)_\n")
    items = d.get("items", [])
    # status fields vary; try common shapes
    status_counts = Counter()
    for item in items:
        st = item.get("status", {}) or {}
        # peerStatuses list or single status
        peers = st.get("peers") or st.get("sessionState") or []
        if isinstance(peers, list) and peers:
            for p in peers:
                if isinstance(p, dict):
                    status_counts[str(p.get("bgpStatus") or p.get("status")
                                      or p.get("sessionState") or "unknown")] += 1
                else:
                    status_counts[str(p)] += 1
        else:
            status_counts[str(st.get("status") or st.get("bgpStatus")
                              or "present")] += 1
    rows = [[k, str(v)] for k, v in sorted(status_counts.items())]
    return ("## BGPSessionState (summary)\n\n"
            f"_FRR-K8s session objects: {len(items)} total. "
            f"Roll-up by reported status (not per-object dump)._\n\n"
            + md_table(["Status / key", "Count"], rows
                       if rows else [["(no status fields parsed)",
                                     str(len(items))]]))


def frr_summary():
    cfg = oc_json(["get", "frrconfigurations", "-A"])
    nodes = oc_json(["get", "frrnodestates"])
    cfg_n = len((cfg or {}).get("items", [])) if cfg else None
    node_n = len((nodes or {}).get("items", [])) if nodes else None
    rows = [
        ["FRRConfiguration", "get-failed" if cfg is None else str(cfg_n)],
        ["FRRNodeState", "get-failed" if nodes is None else str(node_n)],
    ]
    return ("## FRR (summary)\n\n"
            "_FRR-K8s companion objects — counts only; config dumps are "
            "noisy for reference docs._\n\n"
            + md_table(["Kind", "Count"], rows))


# ---------- main ----------
def main():
    print("# OpenShift Network Reference — MetalLB\n")
    server = oc_text(["whoami", "--show-server"])
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print(f"_Server:_ `{server}`  ·  _Generated:_ {stamp}\n")
    print("> Point-in-time snapshot of live cluster state. Values drift — "
          "regenerate before relying on specifics.\n")
    print("> Scope: MetalLB + LB-tied EgressService. "
          "**Not in scope:** host underlay (core), OVN EgressIP / Multus "
          "(Extended Networking).\n")

    peers = bgp_peers()
    if "_could not retrieve" in peers:
        sys.exit("error: could not fetch MetalLB resources from the cluster — "
                 "check connectivity and login; no report written")

    print(metallb_cr())
    print(bfd_profiles())
    print(peers)
    print(ip_pools())
    print(bgp_advertisements())
    print(l2_advertisements())
    print(lb_services())
    print(egress_services())
    print(service_bgp_status_summary())
    print(bgp_session_state_summary())
    print(frr_summary())


if __name__ == "__main__":
    main()
