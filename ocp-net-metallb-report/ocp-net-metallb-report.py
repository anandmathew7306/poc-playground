#!/usr/bin/env python3
"""
ocp-net-metallb-report.py — generate a MetalLB reference report for an
OpenShift cluster.

Covers MetalLB / load-balancer networking: BGP peers, IP address pools,
BGP advertisements and LoadBalancer services. Host/node networking is covered
by the sibling ocp-net-core-report script; ocp-net-report combines both.

Read-only. Runs `oc get ... -o json` and prints markdown tables.
Requires: python3 + oc (logged in). No pip packages.

Usage:
    python3 ocp-net-metallb-report.py                 # print to stdout
    python3 ocp-net-metallb-report.py > report.md     # save to file
"""

import json
import subprocess
import sys
from datetime import datetime


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


def oc_text(args):
    """Run `oc <args>` and return stripped stdout ('' on failure)."""
    try:
        return subprocess.run(["oc"] + args, capture_output=True,
                              text=True).stdout.strip()
    except Exception:
        return ""


def md_table(headers, rows):
    if not rows:
        return "_no data_\n"
    h = "| " + " | ".join(headers) + " |"
    s = "|" + "|".join(["---"] * len(headers)) + "|"
    r = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([h, s] + r) + "\n"


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
    print("# OpenShift Network Reference — MetalLB\n")
    server = oc_text(["whoami", "--show-server"])
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print(f"_Server:_ `{server}`  ·  _Generated:_ {stamp}\n")
    print("> Point-in-time snapshot of live cluster state. Values drift — "
          "regenerate before relying on specifics.\n")

    peers = bgp_peers()
    if "_could not retrieve" in peers:
        sys.exit("error: could not fetch MetalLB resources from the cluster — "
                 "check connectivity and login; no report written")
    print(peers)
    print(ip_pools())
    print(bgp_advertisements())
    print(lb_services())


if __name__ == "__main__":
    main()
