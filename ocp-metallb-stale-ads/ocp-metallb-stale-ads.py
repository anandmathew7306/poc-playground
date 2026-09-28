#!/usr/bin/env python3
"""Read-only check for two MetalLB leftovers.

1. An ad names a pool or peer that is not on the cluster.
2. A pool or peer is on the cluster, but no ad names it.

An empty pool list on an ad means every pool. An empty peer list means every peer.
Those objects are not leftovers.

Runs `oc get` and `oc whoami` only. Does not print addresses or prefixes.

Runs `oc get` and `oc whoami` only. Does not print addresses or prefixes.
Stdlib only. Requires python3 and oc, already logged in.

Usage:
    python3 ocp-metallb-stale-ads.py
    python3 ocp-metallb-stale-ads.py > stale-ads.md

This script is generic. Live output names the cluster you are logged into.
Save that output in a private notes repo. Do not commit it here.
"""

from __future__ import print_function

import json
import subprocess
import sys


def oc_run(args):
    return subprocess.run(
        ["oc"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


def oc_text(args):
    result = oc_run(args)
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def oc_json(args):
    result = oc_run(args + ["-o", "json"])
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip().splitlines()
        print("failed: oc {0}".format(" ".join(args)), file=sys.stderr)
        if err:
            print(err[-1], file=sys.stderr)
        return None
    return json.loads(result.stdout)


def names(doc):
    if not doc:
        return set()
    return {item["metadata"]["name"] for item in doc.get("items") or []}


def main():
    who = oc_text(["whoami"]) or "(whoami failed)"
    server = oc_text(["whoami", "--show-server"]) or "(server unknown)"
    pool_doc = oc_json(["get", "ipaddresspool", "-A"])
    peer_doc = oc_json(["get", "bgppeer", "-A"])
    bgp_doc = oc_json(["get", "bgpadvertisement", "-A"])
    l2_doc = oc_json(["get", "l2advertisement", "-A"])
    if None in (pool_doc, peer_doc, bgp_doc, l2_doc):
        return 1

    pools = names(pool_doc)
    peers = names(peer_doc)
    used_pools = set()
    used_peers = set()
    selects_all_pools = False
    selects_all_peers = False
    stale = []
    ok_bgp = 0
    ok_l2 = 0
    for kind, doc in (("BGPAdvertisement", bgp_doc), ("L2Advertisement", l2_doc)):
        for item in doc.get("items") or []:
            spec = item.get("spec") or {}
            want_pools = spec.get("ipAddressPools") or []
            want_peers = spec.get("peers") or []
            if want_pools:
                used_pools.update(want_pools)
            else:
                selects_all_pools = True
            if kind == "BGPAdvertisement":
                if want_peers:
                    used_peers.update(want_peers)
                else:
                    selects_all_peers = True
            missing_pools = [name for name in want_pools if name not in pools]
            missing_peers = [name for name in want_peers if name not in peers]
            if missing_pools or missing_peers:
                stale.append(
                    (
                        item["metadata"]["name"],
                        kind,
                        missing_pools,
                        missing_peers,
                    )
                )
            elif kind == "BGPAdvertisement":
                ok_bgp += 1
            else:
                ok_l2 += 1

    if selects_all_pools:
        leftover_pools = []
    else:
        leftover_pools = sorted(pools - used_pools)
    if selects_all_peers:
        leftover_peers = []
    else:
        leftover_peers = sorted(peers - used_peers)

    bgp_count = len(bgp_doc.get("items") or [])
    l2_count = len(l2_doc.get("items") or [])
    print("# MetalLB stale ads")
    print()
    print("User: {0}".format(who))
    print("Server: {0}".format(server))
    print()
    print("Pools: {0}".format(len(pools)))
    print("BGP peers: {0}".format(len(peers)))
    print("BGP ads: {0}".format(bgp_count))
    print("L2 ads: {0}".format(l2_count))
    print()
    print("Stale ads: {0}".format(len(stale)))
    print("BGP ads wired to existing pools and peers: {0}".format(ok_bgp))
    print("L2 ads wired to existing pools: {0}".format(ok_l2))
    print("Leftover pools: {0}".format(len(leftover_pools)))
    print("Leftover peers: {0}".format(len(leftover_peers)))
    print()
    if not stale:
        print("No ad names a missing pool or peer.")
    else:
        for name, kind, missing_pools, missing_peers in stale:
            print("- {0} ({1})".format(name, kind))
            if missing_pools:
                print("  missing pools: {0}".format(", ".join(missing_pools)))
            if missing_peers:
                print("  missing peers: {0}".format(", ".join(missing_peers)))
    print()
    if not leftover_pools and not leftover_peers:
        print("No leftover pools or peers.")
        return 0
    if leftover_pools:
        print("Pools not named by any ad:")
        for name in leftover_pools:
            print("- {0}".format(name))
    if leftover_pools and leftover_peers:
        print()
    if leftover_peers:
        print("Peers not named by any ad:")
        for name in leftover_peers:
            print("- {0}".format(name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
