#!/usr/bin/env python3
"""
ocp-net-discovery.py — inventory networking-related CRDs and a few built-in
API resources on an OpenShift cluster.

Purpose: see what networking components exist (and have live objects) before
deciding what core / MetalLB / related report scripts should cover.

Read-only. Runs `oc get ...` and prints markdown tables.
Requires: python3 + oc (logged in). No pip packages.

Usage:
    python3 ocp-net-discovery.py                 # print to stdout
    python3 ocp-net-discovery.py > discovery.md  # save to file

This script is generic (safe for public repos). Redirect output that contains
cluster hostnames / counts into a private notes repo if needed.
"""

import json
import re
import subprocess
import sys
from datetime import datetime


# CRD name or API group matches any of these (case-insensitive).
INTEREST_RE = re.compile(
    r"metallb|frrk8s|frr-k8s|ovn|egress|nmstate|whereabouts|"
    r"sriov|multus|net-attach|networkattachment|"
    r"userdefinednetwork|clusteruserdefined|"
    r"adminnetworkpolicy|baselineadminnetworkpolicy|"
    r"egressfirewall|egressqos|egressservice|egressip|"
    r"ipam|bgp|bfd|localnet|"
    r"nodenetwork|"
    # cluster network config (not all of config.openshift.io)
    r"networks?\.config\.openshift\.io|"
    r"ingresses\.config\.openshift\.io|"
    r"infrastructures\.config\.openshift\.io|"
    r"networks?\.operator\.openshift\.io|"
    r"k8s\.ovn\.org|metallb\.io|nmstate\.io|"
    r"k8s\.cni\.cncf\.io|whereaboutscni|"
    r"sriovnetwork\.openshift\.io|"
    r"networking\.k8s\.io|network\.openshift\.io",
    re.I,
)

# Built-in / non-CRD resources worth counting for doc scope.
BUILTINS = [
    # (section label, oc get args for list, notes)
    ("services (type=LoadBalancer)",
     ["get", "svc", "-A", "--field-selector", "spec.type=LoadBalancer"],
     "MetalLB consumers"),
    ("networkpolicies",
     ["get", "networkpolicies", "-A"],
     "namespaced K8s NetworkPolicy"),
    ("egressips (k8s.ovn.org)",
     ["get", "egressips"],
     "OVN EgressIP — core networking home"),
    ("egressservices (k8s.ovn.org)",
     ["get", "egressservices", "-A"],
     "LB-tied egress — MetalLB-adjacent"),
]


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
        err = (e.stderr or "").strip()
        if err:
            # keep stderr short in report context
            print(f"  > {err.splitlines()[-1]}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"  > could not parse JSON: {' '.join(cmd)}", file=sys.stderr)
        return None


def oc_text(args):
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


def suggest_home(group, kind):
    """Tentative documentation home — human review still required."""
    g, k = (group or "").lower(), (kind or "").lower()
    blob = g + "/" + k

    if any(x in blob for x in (
        "metallb", "frrk8s", "frr-k8s", "bgpadvertisement", "bgppeer",
        "ipaddresspool", "l2advertisement", "bfdprofile", "community",
        "servicebgpstatus", "servicel2status",
    )):
        return "metallb"
    if "egressservice" in blob:
        return "metallb-adjacent"
    if any(x in blob for x in (
        "egressip", "egressfirewall", "egressqos", "egressrouter",
        "adminnetworkpolicy", "baselineadminnetworkpolicy",
        "networkpolicy",
    )):
        return "core (ovn/policy)"
    if any(x in blob for x in (
        "nmstate", "nodenetworkstate", "nodenetworkconfiguration",
        "sriov", "whereabouts", "networkattachment", "userdefinednetwork",
        "clusteruserdefined", "localnet",
    )):
        return "core (host/cni)"
    if any(x in blob for x in (
        "config.openshift.io", "network.openshift.io", "operator.openshift.io",
    )):
        return "core (cluster-config)"
    return "review"


def crd_interesting(crd):
    name = crd.get("metadata", {}).get("name", "")
    group = crd.get("spec", {}).get("group", "")
    return bool(INTEREST_RE.search(name) or INTEREST_RE.search(group))


def resource_count(group, resource, namespaced):
    """Count live objects; return (count_or_None, error_hint)."""
    # Prefer plural.group form for disambiguation when group is set.
    if group:
        target = f"{resource}.{group}"
    else:
        target = resource
    args = ["get", target]
    if namespaced:
        args.append("-A")
    data = oc_json(args)
    if data is None:
        return None, "get-failed"
    return len(data.get("items", [])), ""


def discover_crds():
    data = oc_json(["get", "crd"])
    if not data:
        return None

    rows = []
    for crd in data.get("items", []):
        if not crd_interesting(crd):
            continue
        meta = crd.get("metadata", {})
        spec = crd.get("spec", {})
        name = meta.get("name", "")
        group = spec.get("group", "")
        scope = spec.get("scope", "")
        versions = spec.get("versions", []) or []
        stored = next((v.get("name") for v in versions if v.get("storage")),
                      (versions[0].get("name") if versions else "-"))
        kinds = spec.get("names", {}) or {}
        kind = kinds.get("kind", "")
        plural = kinds.get("plural", "")
        namespaced = scope == "Namespaced"

        count, err = resource_count(group, plural, namespaced)
        count_s = err if count is None else str(count)
        present = "yes" if (count or 0) > 0 else "no"

        rows.append({
            "kind": kind,
            "name": name,
            "group": group,
            "scope": scope,
            "version": stored,
            "count": count_s,
            "present": present,
            "home": suggest_home(group, kind),
            "_sort": (group, kind),
        })

    rows.sort(key=lambda r: r["_sort"])
    return rows


def discover_builtins():
    rows = []
    for label, args, note in BUILTINS:
        data = oc_json(args)
        if data is None:
            rows.append([label, "get-failed", note])
            continue
        n = len(data.get("items", []))
        rows.append([label, str(n), note])
    return rows


def main():
    print("# OpenShift Network Discovery\n")
    server = oc_text(["whoami", "--show-server"])
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print(f"_Server:_ `{server}`  ·  _Generated:_ {stamp}\n")
    print("> Read-only inventory of networking-related CRDs and selected "
          "built-in resources. Counts are point-in-time. "
          "**Suggested home** is a heuristic for documentation/script "
          "ownership — confirm before acting.\n")

    crds = discover_crds()
    if crds is None:
        sys.exit("error: could not list CRDs — check connectivity and login")

    print("## Networking-related CRDs\n")
    print("_Filtered by name/API-group keywords (metallb, ovn, egress, "
          "nmstate, cni, sriov, …)._\n")
    table_rows = [
        [r["kind"], r["group"], r["scope"], r["version"],
         r["count"], r["present"], r["home"]]
        for r in crds
    ]
    print(md_table(
        ["Kind", "Group", "Scope", "Version", "Count", "Has objects",
         "Suggested home"],
        table_rows,
    ))

    present = [r for r in crds if r["present"] == "yes"]
    empty = [r for r in crds if r["present"] == "no"]
    failed = [r for r in crds if r["count"] == "get-failed"]

    print("## Summary\n")
    print(md_table(
        ["Bucket", "Count"],
        [
            ["CRDs matched filter", str(len(crds))],
            ["With live objects", str(len(present))],
            ["Registered but empty", str(len(empty))],
            ["Count get-failed", str(len(failed))],
        ],
    ))

    if present:
        print("### Present (has objects)\n")
        print(", ".join(sorted({r["kind"] for r in present})) + "\n")

    if empty:
        print("### Registered but empty\n")
        print(", ".join(sorted({r["kind"] for r in empty})) + "\n")

    print("## Built-in / convenience counts\n")
    print("_Same resources may also appear above as CRDs; listed here for "
          "quick cross-check._\n")
    print(md_table(["Resource", "Count", "Notes"], discover_builtins()))

    print("## How to use this report\n")
    print(
        "1. Prefer **Present** kinds for report-script coverage.\n"
        "2. Map each kind to **core**, **metallb**, or **skip** "
        "(empty CRDs can wait).\n"
        "3. Re-run on NPE and prod before freezing script scope.\n"
        "4. Keep live discovery output in a private notes repo; this script "
        "stays generic.\n"
    )


if __name__ == "__main__":
    main()
