#!/usr/bin/env python3
"""
ocp-net-discovery.py — inventory networking-related CRDs and a few built-in
API resources on an OpenShift cluster.

Purpose: see what networking components exist (and have live objects) before
deciding what core / MetalLB / Extended report scripts should cover.

Read-only. Runs `oc get ...` and prints markdown tables.
Requires: python3 + oc (logged in). No pip packages.

Usage:
    python3 ocp-net-discovery.py                 # print to stdout
    python3 ocp-net-discovery.py > discovery.md  # save to file

This script is generic (safe for public repos). Redirect output that contains
cluster hostnames / counts into a private notes repo if needed.
"""

import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime


# CRD name or API group matches any of these (case-insensitive).
# Avoid bare "ipam" (pulls ipam.cluster.x-k8s.io) and unanchored
# networking.k8s.io (also matches gateway.networking.k8s.io).
INTEREST_RE = re.compile(
    r"metallb|frrk8s|frr-k8s|ovn|egress|nmstate|whereabouts|"
    r"sriov|multus|net-attach|networkattachment|"
    r"userdefinednetwork|clusteruserdefined|"
    r"adminnetworkpolicy|baselineadminnetworkpolicy|"
    r"egressfirewall|egressqos|egressservice|egressip|"
    r"ipamclaim|bgp|bfd|localnet|"
    r"nodenetwork|"
    r"networks?\.config\.openshift\.io|"
    r"ingresses\.config\.openshift\.io|"
    r"infrastructures\.config\.openshift\.io|"
    r"networks?\.operator\.openshift\.io|"
    r"k8s\.ovn\.org|metallb\.io|nmstate\.io|"
    r"k8s\.cni\.cncf\.io|whereaboutscni|"
    r"sriovnetwork\.openshift\.io|"
    r"network\.openshift\.io|"
    # K8s NetworkPolicy API group only (not Gateway API)
    r"(^|\.)networking\.k8s\.io$|"
    r"^networkpolicies\.networking\.k8s\.io$",
    re.I,
)

# Groups to drop even if the keyword regex matches (noise for doc inventory).
EXCLUDE_GROUP_SUFFIXES = (
    "gateway.networking.k8s.io",
    "ipam.cluster.x-k8s.io",
)

# Built-in / convenience counts (some overlap CRDs — intentional cross-check).
BUILTINS = [
    # (section label, oc get args before -o name, notes)
    ("services (type=LoadBalancer)",
     ["get", "svc", "-A", "--field-selector", "spec.type=LoadBalancer"],
     "MetalLB consumers"),
    ("networkpolicies",
     ["get", "networkpolicies", "-A"],
     "namespaced K8s NetworkPolicy"),
    ("egressips (k8s.ovn.org)",
     ["get", "egressips"],
     "OVN EgressIP — Extended Networking"),
    ("egressservices (k8s.ovn.org)",
     ["get", "egressservices", "-A"],
     "LB-tied egress — MetalLB-adjacent"),
    ("network-attachment-definitions",
     ["get", "network-attachment-definitions", "-A"],
     "Multus NAD — Extended Networking"),
    ("multi-networkpolicies",
     ["get", "multi-networkpolicies.k8s.cni.cncf.io", "-A"],
     "MultiNetworkPolicy — Extended Networking"),
    ("ippools (whereabouts)",
     ["get", "ippools.whereabouts.cni.cncf.io", "-A"],
     "Whereabouts IPPool — Extended Networking"),
]

COUNT_WORKERS = 8


def oc_run(args, check=True):
    """Run `oc <args>`; return CompletedProcess (or raise if check and fail)."""
    return subprocess.run(
        ["oc"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=check,
    )


def oc_json(args):
    """Run `oc <args> -o json` and return parsed JSON (or None on failure)."""
    import json
    try:
        out = oc_run(args + ["-o", "json"], check=True)
        return json.loads(out.stdout)
    except subprocess.CalledProcessError as e:
        print(f"  > command failed: oc {' '.join(args)} -o json", file=sys.stderr)
        err = (e.stderr or "").strip()
        if err:
            print(f"  > {err.splitlines()[-1]}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"  > could not parse JSON: oc {' '.join(args)}", file=sys.stderr)
        return None


def oc_text(args):
    try:
        return oc_run(args, check=False).stdout.strip()
    except Exception:
        return ""


def oc_count(args):
    """
    Count objects cheaply via `oc get ... -o name` (one name per line).
    Returns (count_or_None, error_hint).
    """
    try:
        out = oc_run(args + ["-o", "name"], check=True)
        n = sum(1 for ln in out.stdout.splitlines() if ln.strip())
        return n, ""
    except subprocess.CalledProcessError as e:
        print(f"  > command failed: oc {' '.join(args)} -o name", file=sys.stderr)
        err = (e.stderr or "").strip()
        if err:
            print(f"  > {err.splitlines()[-1]}", file=sys.stderr)
        return None, "get-failed"


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
    # Locked Extended: EgressIP + Multus (NAD / Whereabouts / MultiNetworkPolicy)
    if any(x in blob for x in (
        "egressip",
        "whereabouts",
        "networkattachment",
        "multinetworkpolicy",
    )):
        return "extended"
    if any(x in blob for x in (
        "egressfirewall", "egressqos", "egressrouter",
        "adminnetworkpolicy", "baselineadminnetworkpolicy",
        "networkpolicy",
    )):
        return "core (ovn/policy)"
    if any(x in blob for x in (
        "nmstate", "nodenetworkstate", "nodenetworkconfiguration",
        "sriov", "userdefinednetwork", "clusteruserdefined", "localnet",
    )):
        return "core (host/cni)"
    if any(x in blob for x in (
        "config.openshift.io", "network.openshift.io", "operator.openshift.io",
    )):
        return "core (cluster-config)"
    return "review"


def crd_interesting(crd):
    name = crd.get("metadata", {}).get("name", "")
    group = crd.get("spec", {}).get("group", "") or ""
    # Drop known noise even if a keyword substring matches
    if any(group == sfx or group.endswith("." + sfx)
           for sfx in EXCLUDE_GROUP_SUFFIXES):
        return False
    if "gateway.networking.k8s.io" in name:
        return False
    return bool(INTEREST_RE.search(name) or INTEREST_RE.search(group))


def resource_count(group, resource, namespaced):
    """Count live objects; return (count_or_None, error_hint)."""
    if group:
        target = f"{resource}.{group}"
    else:
        target = resource
    args = ["get", target]
    if namespaced:
        args.append("-A")
    return oc_count(args)


def _count_crd_row(meta_row):
    """Worker: fill count/present on a CRD row dict (mutates copy)."""
    r = dict(meta_row)
    count, err = resource_count(r["group"], r["plural"], r["namespaced"])
    if count is None:
        r["count"] = err or "get-failed"
        r["present"] = "unknown"
    else:
        r["count"] = str(count)
        r["present"] = "yes" if count > 0 else "no"
    return r


def discover_crds():
    data = oc_json(["get", "crd"])
    if not data:
        return None

    pending = []
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

        pending.append({
            "kind": kind,
            "name": name,
            "group": group,
            "scope": scope,
            "version": stored,
            "plural": plural,
            "namespaced": namespaced,
            "home": suggest_home(group, kind),
            "_sort": (group, kind),
        })

    rows = []
    with ThreadPoolExecutor(max_workers=COUNT_WORKERS) as pool:
        futs = [pool.submit(_count_crd_row, p) for p in pending]
        for fut in as_completed(futs):
            rows.append(fut.result())

    rows.sort(key=lambda r: r["_sort"])
    return rows


def discover_builtins():
    rows = []

    def one(item):
        label, args, note = item
        n, err = oc_count(args)
        if n is None:
            return [label, err or "get-failed", note]
        return [label, str(n), note]

    with ThreadPoolExecutor(max_workers=COUNT_WORKERS) as pool:
        futs = {pool.submit(one, b): b[0] for b in BUILTINS}
        # Preserve BUILTINS order
        by_label = {futs[f]: f.result() for f in as_completed(futs)}
    return [by_label[b[0]] for b in BUILTINS]


def home_rollup(crds):
    """Count present CRDs per suggested home."""
    buckets = {}
    for r in crds:
        if r["present"] != "yes":
            continue
        buckets[r["home"]] = buckets.get(r["home"], 0) + 1
    return sorted(buckets.items(), key=lambda x: x[0])


def main():
    print("# OpenShift Network Discovery\n")
    server = oc_text(["whoami", "--show-server"])
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print(f"_Server:_ `{server}`  ·  _Generated:_ {stamp}\n")
    print("> Read-only inventory of networking-related CRDs and selected "
          "built-in resources. Counts are point-in-time (`oc get -o name`). "
          "**Suggested home** is a heuristic for documentation/script "
          "ownership — confirm before acting.\n")

    crds = discover_crds()
    if crds is None:
        sys.exit("error: could not list CRDs — check connectivity and login")

    print("## Networking-related CRDs\n")
    print("_Filtered by name/API-group keywords (metallb, ovn, egress, "
          "nmstate, cni, sriov, …). Gateway API / cluster-api IPAM excluded._\n")
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
    failed = [r for r in crds if r["count"] == "get-failed"
              or r["present"] == "unknown"]
    empty = [r for r in crds
             if r["present"] == "no" and r["count"] != "get-failed"]

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

    rollup = home_rollup(crds)
    if rollup:
        print("### Present by suggested home\n")
        print(md_table(
            ["Suggested home", "Kinds with objects"],
            [[home, str(n)] for home, n in rollup],
        ))

    if present:
        print("### Present (has objects)\n")
        print(", ".join(sorted({r["kind"] for r in present})) + "\n")

    if empty:
        print("### Registered but empty\n")
        print(", ".join(sorted({r["kind"] for r in empty})) + "\n")

    if failed:
        print("### Count get-failed\n")
        print(", ".join(sorted({r["kind"] for r in failed})) + "\n")

    print("## Built-in / convenience counts\n")
    print("_Same resources may also appear above as CRDs; listed here for "
          "quick cross-check._\n")
    print(md_table(["Resource", "Count", "Notes"], discover_builtins()))

    print("## How to use this report\n")
    print(
        "1. Prefer **Present** kinds for report-script coverage.\n"
        "2. Map each kind to **core**, **metallb**, **extended**, or **skip** "
        "(empty CRDs can wait). Confirm **Suggested home** — especially "
        "`extended` (EgressIP, NAD, Whereabouts, MultiNetworkPolicy).\n"
        "3. Re-run on NPE and prod (all sites) before freezing script scope.\n"
        "4. Keep live discovery output in a private notes repo; this script "
        "stays generic.\n"
    )


if __name__ == "__main__":
    main()
