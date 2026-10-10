#!/usr/bin/env python3
"""
ocp-metallb-cleanup-check.py — read-only facts for a MetalLB cleanup on one cluster.

Sections:
  1. Summary counts
  2. Stale ads: ads that name a pool or peer that is not on the cluster, with
     the references that still work (delete the ad, or edit it?)
  3. Leftover pools: pools no ad selects, with the services that hold an IP
     from them or ask for them
  4. Leftover peers: peers no BGP ad names, with their BGP session state
  5. LoadBalancer services with no IP, and the pool they ask for
  6. Git vs live: pools, peers and ads in the ACM policy copies on this
     cluster (or in Git with --git) compared with the live objects

Ad rules (same as MetalLB):
  - ipAddressPools and ipAddressPoolSelectors both empty: the ad selects every pool
  - peers empty on a BGP ad: the ad uses every peer
  - ipAddressPoolSelectors are matched against pool labels

Uses `oc get` and `oc whoami` only. Never reads Secrets. Never prints peer
passwords, addresses or prefixes; only object names, VRF names and counts.
Requires: python3 + oc (logged in). Stdlib only, plus PyYAML when --git is used.

Usage:
    python3 ocp-metallb-cleanup-check.py --server https://api.example:6443 > metallb.md
    python3 ocp-metallb-cleanup-check.py --server https://api.example:6443 \\
        --git /path/to/repo/env/policygentemplates > metallb.md

Refuses to continue unless `oc whoami --show-server` matches --server.
Redirect stdout into a private notes repo. Do not commit live output here.
"""

from __future__ import print_function

import argparse
import ipaddress
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime


KINDS = ("IPAddressPool", "BGPPeer", "BGPAdvertisement", "L2Advertisement")
POOL_ANN = ("metallb.io/address-pool", "metallb.universe.tf/address-pool")
ALLOC_ANN = ("metallb.io/ip-allocated-from-pool", "metallb.universe.tf/ip-allocated-from-pool")


def oc_run(args):
    return subprocess.run(
        ["oc"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def oc_items(args, optional=False):
    p = oc_run(args + ["-o", "json"])
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()
        if optional and "doesn't have a resource type" in err.lower():
            return None
        lines = err.splitlines()
        die("oc {0} failed: {1}".format(" ".join(args), lines[-1] if lines else p.returncode))
    try:
        return (json.loads(p.stdout) or {}).get("items") or []
    except ValueError:
        die("oc {0} did not return json".format(" ".join(args)))


def norm_server(url):
    return (url or "").strip().rstrip("/")


def md_table(headers, rows):
    if not rows:
        return "_none_\n"
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join(["---"] * len(headers)) + "|"
    body = []
    for row in rows:
        cells = []
        for cell in row:
            text = "-" if cell in (None, "") else str(cell)
            cells.append(text.replace("|", "\\|").replace("\n", " "))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([head, sep] + body) + "\n"


def join(values):
    return ", ".join(sorted(values)) if values else "-"


def name(obj):
    return (obj.get("metadata") or {}).get("name") or ""


def norm_ip(addr):
    """Normalise an address. BGPSessionState writes IPv6 with '-' instead of ':'."""
    addr = addr or ""
    for candidate in (addr, addr.replace("-", ":")):
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            continue
    return addr


def selector_matches(selector, labels):
    for k, v in (selector.get("matchLabels") or {}).items():
        if labels.get(k) != v:
            return False
    for expr in selector.get("matchExpressions") or []:
        key, op, vals = expr.get("key"), expr.get("operator"), expr.get("values") or []
        if op == "In" and labels.get(key) not in vals:
            return False
        if op == "NotIn" and labels.get(key) in vals:
            return False
        if op == "Exists" and key not in labels:
            return False
        if op == "DoesNotExist" and key in labels:
            return False
    return True


def pool_contains(pool, ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in (pool.get("spec") or {}).get("addresses") or []:
        entry = entry.strip()
        try:
            if "-" in entry:
                lo, hi = [ipaddress.ip_address(x.strip()) for x in entry.split("-", 1)]
                if lo.version == addr.version and lo <= addr <= hi:
                    return True
            elif addr in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


# ---------------------------------------------------------------- policy / git


def policy_metallb(policies):
    """Names of MetalLB objects in musthave/mustonlyhave templates of the policy copies."""
    out = defaultdict(set)
    for pol in policies:
        for tmpl in (pol.get("spec") or {}).get("policy-templates") or []:
            cfg = tmpl.get("objectDefinition") or {}
            if cfg.get("kind") != "ConfigurationPolicy":
                continue
            for ot in (cfg.get("spec") or {}).get("object-templates") or []:
                if (ot.get("complianceType") or "musthave").lower() == "mustnothave":
                    continue
                obj = ot.get("objectDefinition") or {}
                if obj.get("kind") in KINDS and (obj.get("apiVersion") or "").startswith("metallb.io/"):
                    out[obj["kind"]].add(name(obj))
    return out


def git_metallb(root, cluster_name):
    try:
        import yaml
    except ImportError:
        die("--git needs PyYAML (pip install pyyaml)")

    def docs(path):
        with open(path) as f:
            return [d for d in yaml.safe_load_all(f) if isinstance(d, dict)]

    kust = None
    for fname in ("kustomization.yml", "kustomization.yaml"):
        if os.path.exists(os.path.join(root, fname)):
            kust = docs(os.path.join(root, fname))[0]
    if kust is None:
        die("no kustomization.yml in {0}".format(root))
    pgts = []
    for gen in kust.get("generators") or []:
        pgts += [p for p in docs(os.path.join(root, gen)) if p.get("kind") == "PolicyGenTemplate"]
    # Per-cluster PolicyGenTemplates are bound by a label whose value is the cluster name.
    keys = {k for p in pgts for k, v in ((p.get("spec") or {}).get("bindingRules") or {}).items() if v == cluster_name}
    out, used, problems = defaultdict(set), [], []
    for p in pgts:
        rules = (p.get("spec") or {}).get("bindingRules") or {}
        if any(k in rules and rules[k] != cluster_name for k in keys):
            continue
        used.append(name(p))
        for sf in (p.get("spec") or {}).get("sourceFiles") or []:
            path = os.path.join(root, "source-crs", sf.get("fileName") or "")
            if not os.path.exists(path):
                problems.append("missing source file: {0}".format(sf.get("fileName")))
                continue
            for d in docs(path):
                if d.get("kind") in KINDS and (d.get("apiVersion") or "").startswith("metallb.io/"):
                    out[d["kind"]].add((sf.get("metadata") or {}).get("name") or name(d))
    return out, used, problems


# ---------------------------------------------------------------- main


def main():
    parser = argparse.ArgumentParser(description="Read-only MetalLB cleanup facts")
    parser.add_argument("--server", required=True, help="API server URL that oc must already be logged into")
    parser.add_argument("--git", help="path to a policygentemplates folder (with kustomization.yml)")
    args = parser.parse_args()

    expected = norm_server(args.server)
    who = oc_run(["whoami"])
    server = oc_run(["whoami", "--show-server"])
    if who.returncode != 0 or server.returncode != 0:
        die("oc whoami failed. Log in before running this script.")
    actual = norm_server(server.stdout)
    if actual != expected:
        die("refusing: oc server is {0}, --server is {1}".format(actual, expected))

    pools = oc_items(["get", "ipaddresspools.metallb.io", "-A"])
    peers = oc_items(["get", "bgppeers.metallb.io", "-A"])
    bgp_ads = oc_items(["get", "bgpadvertisements.metallb.io", "-A"])
    l2_ads = oc_items(["get", "l2advertisements.metallb.io", "-A"])
    services = [s for s in oc_items(["get", "services", "-A"]) if (s.get("spec") or {}).get("type") == "LoadBalancer"]
    sessions = oc_items(["get", "bgpsessionstates.frrk8s.metallb.io", "-A"], optional=True)
    policies = oc_items(["get", "policies.policy.open-cluster-management.io", "-A"], optional=True) or []

    pool_by_name = {name(p): p for p in pools}
    peer_names = {name(p) for p in peers}
    cluster_name = next(((pol.get("metadata") or {}).get("namespace") for pol in policies), "")
    in_policy = policy_metallb(policies)

    # ---- ads
    used_pools, used_peers = set(), set()
    stale = []
    ad_pools = {}
    for kind, items in (("BGPAdvertisement", bgp_ads), ("L2Advertisement", l2_ads)):
        for ad in items:
            spec = ad.get("spec") or {}
            named = spec.get("ipAddressPools") or []
            selectors = spec.get("ipAddressPoolSelectors") or []
            if not named and not selectors:
                selected = set(pool_by_name)
            else:
                selected = {n for n in named if n in pool_by_name}
                for sel in selectors:
                    selected |= {n for n, p in pool_by_name.items()
                                 if selector_matches(sel, (p.get("metadata") or {}).get("labels") or {})}
            used_pools |= selected
            ad_pools[(kind, name(ad))] = selected
            want_peers = (spec.get("peers") or []) if kind == "BGPAdvertisement" else []
            if kind == "BGPAdvertisement":
                used_peers |= set(want_peers) if want_peers else set(peer_names)
            missing_pools = [n for n in named if n not in pool_by_name]
            missing_peers = [n for n in want_peers if n not in peer_names]
            if missing_pools or missing_peers:
                stale.append({
                    "kind": kind, "name": name(ad), "missing_pools": missing_pools, "missing_peers": missing_peers,
                    "ok_pools": sorted(selected), "ok_peers": sorted(n for n in want_peers if n in peer_names),
                    "selectors": bool(selectors),
                })

    for s in stale:
        others = set()
        for (k, n), sel in ad_pools.items():
            if (k, n) != (s["kind"], s["name"]):
                others |= sel
        s["ok_pools_elsewhere"] = sorted(p for p in s["ok_pools"] if p in others)
        if not s["ok_pools"] and (s["kind"] == "L2Advertisement" or not s["ok_peers"]):
            s["refs"] = "all named pools and peers missing"
        elif not s["ok_pools"]:
            s["refs"] = "all named pools missing"
        elif s["kind"] == "BGPAdvertisement" and not s["ok_peers"] and s["missing_peers"]:
            s["refs"] = "all named peers missing"
        else:
            s["refs"] = "partly missing"

    leftover_pools = sorted(set(pool_by_name) - used_pools)
    leftover_peers = sorted(peer_names - used_peers)

    # ---- services
    holds, asks, no_ip = defaultdict(list), defaultdict(list), []
    for svc in services:
        md = svc.get("metadata") or {}
        ann = md.get("annotations") or {}
        sname = "{0}/{1}".format(md.get("namespace"), md.get("name"))
        ingress = ((svc.get("status") or {}).get("loadBalancer") or {}).get("ingress") or []
        ips = [i.get("ip") for i in ingress if i.get("ip")]
        requested = next((ann[k] for k in POOL_ANN if ann.get(k)), "")
        if requested:
            asks[requested].append(sname)
        alloc = next((ann[k] for k in ALLOC_ANN if ann.get(k)), "")
        if ips:
            pool = alloc or next((n for n, p in pool_by_name.items() if any(pool_contains(p, ip) for ip in ips)), "")
            holds[pool or "(no matching pool)"].append(sname)
        else:
            no_ip.append([sname, requested or "-", ("yes" if requested in pool_by_name else "no") if requested else "-"])

    # ---- sessions
    peer_sessions = {}
    unmatched_addrs = set()
    if sessions is not None:
        addr_to_peer = {}
        for p in peers:
            sp = p.get("spec") or {}
            addr_to_peer[(norm_ip(sp.get("peerAddress")), sp.get("vrf") or "")] = name(p)
        for s in sessions:
            st = s.get("status") or {}
            key = (norm_ip(st.get("peer")), st.get("vrf") or "")
            pname = addr_to_peer.get(key)
            if pname:
                peer_sessions.setdefault(pname, Counter())[st.get("bgpStatus") or "unknown"] += 1
            else:
                unmatched_addrs.add(key)

    def pol_mark(kind, n):
        return "yes" if n in in_policy.get(kind, set()) else "no"

    # ------------------------------------------------------------ output
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print("# MetalLB cleanup check\n")
    print("_Server:_ `{0}`  ·  _Cluster:_ `{1}`  ·  _Generated:_ {2}  ·  _Read-only (`oc get` / `oc whoami`)._\n"
          .format(actual, cluster_name or "-", stamp))
    print("> Save this file in a **private** notes repo. Do not commit live output next to this script.\n")

    print("## 1. Summary\n")
    print(md_table(["Item", "Count"], [
        ["Pools", len(pools)], ["BGP peers", len(peers)], ["BGP ads", len(bgp_ads)], ["L2 ads", len(l2_ads)],
        ["**Stale ads**", "**{0}**".format(len(stale))],
        ["- all named pools / peers missing", sum(1 for s in stale if s["refs"] != "partly missing")],
        ["- partly missing (some references still work)", sum(1 for s in stale if s["refs"] == "partly missing")],
        ["**Leftover pools**", "**{0}**".format(len(leftover_pools))],
        ["- holding service IPs", sum(1 for p in leftover_pools if holds.get(p))],
        ["**Leftover peers**", "**{0}**".format(len(leftover_peers))],
        ["LoadBalancer services", len(services)],
        ["- with no IP", len(no_ip)],
    ]))

    print("## 2. Stale ads\n")
    print(md_table(
        ["Ad", "Kind", "References", "Missing pools", "Missing peers", "Pools still selected",
         "Of those, also selected by another ad", "Peers still named", "In policy"],
        [[s["name"], s["kind"], s["refs"], join(s["missing_pools"]), join(s["missing_peers"]),
          join(s["ok_pools"]), join(s["ok_pools_elsewhere"]), join(s["ok_peers"]), pol_mark(s["kind"], s["name"])]
         for s in sorted(stale, key=lambda x: x["name"])]))

    print("## 3. Leftover pools\n")
    print("A leftover pool is selected by no ad, so its addresses are not announced.\n")
    print(md_table(
        ["Pool", "autoAssign", "Services holding an IP from it", "Services asking for it", "In policy"],
        [[p, (pool_by_name[p].get("spec") or {}).get("autoAssign", True),
          "{0}: {1}".format(len(holds[p]), join(holds[p])) if holds.get(p) else "0",
          "{0}: {1}".format(len(asks[p]), join(asks[p])) if asks.get(p) else "0",
          pol_mark("IPAddressPool", p)] for p in leftover_pools]))

    print("## 4. Leftover peers\n")
    print("A leftover peer is named by no BGP ad. It still opens a BGP session.\n")
    rows = []
    for p in leftover_peers:
        obj = next(x for x in peers if name(x) == p)
        sess = peer_sessions.get(p)
        state = "-" if sessions is None else (join("{0} x{1}".format(k, v) for k, v in sess.items()) if sess else "no session")
        rows.append([p, (obj.get("spec") or {}).get("vrf") or "default", state, pol_mark("BGPPeer", p)])
    print(md_table(["Peer", "VRF", "BGP sessions (per node)", "In policy"], rows))

    print("## 5. LoadBalancer services with no IP\n")
    print(md_table(["Service", "Pool asked for", "Pool exists"], sorted(no_ip)))

    print("## 6. Git vs live\n")
    if args.git:
        ref, used, problems = git_metallb(args.git, cluster_name)
        print("Source: Git `{0}` (PolicyGenTemplates: {1}).\n".format(
            os.path.basename(os.path.dirname(os.path.abspath(args.git))) + "/" + os.path.basename(os.path.abspath(args.git)),
            join(used)))
        for p in problems:
            print("- " + p)
    else:
        ref = in_policy
        print("Source: ACM policy copies on this cluster.\n")
    live = {"IPAddressPool": set(pool_by_name), "BGPPeer": peer_names,
            "BGPAdvertisement": {name(a) for a in bgp_ads}, "L2Advertisement": {name(a) for a in l2_ads}}
    rows, totals = [], [0, 0, 0, 0, 0]
    for k in KINDS:
        g, lv = ref.get(k, set()), live[k]
        r = [len(g), len(lv), len(g & lv), len(g - lv), len(lv - g)]
        totals = [a + b for a, b in zip(totals, r)]
        rows.append([k] + r)
    rows.append(["**Total**"] + ["**{0}**".format(t) for t in totals])
    print(md_table(["Kind", "Git", "Live", "In both", "Git only", "Live only"], rows))
    for k in KINDS:
        g, lv = ref.get(k, set()), live[k]
        if g - lv:
            print("- {0} in Git only: {1}".format(k, join(g - lv)))
        if lv - g:
            print("- {0} live only: {1}".format(k, join(lv - g)))
    print()

    print("## Notes\n")
    print("- \"In policy\" = the object name is in an ACM policy copy on this cluster (what the hub placed from Git).")
    if sessions is None:
        print("- BGP session state not available on this cluster (no BGPSessionState kind).")
    elif unmatched_addrs:
        print("- {0} BGP session peer address(es) match no BGPPeer by address and VRF. Not expanded here.".format(
            len(unmatched_addrs)))
    print("- Peer passwords, addresses and prefixes are never printed. Secrets are never read.")


if __name__ == "__main__":
    main()
