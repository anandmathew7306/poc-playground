#!/usr/bin/env python3
"""Read-only IPv4 address count for VLAN node subnets and MetalLB pools.

A node subnet drops the network and broadcast addresses. A MetalLB pool
counts every address in its range. A pool is grouped with the VLAN whose
BGP peers it is announced to. The pool prefix does not have to sit inside
the node subnet.

Runs `oc get` and `oc whoami` only. Stdlib only.

Usage:
    python3 ocp-vlan-ip-capacity.py
    python3 ocp-vlan-ip-capacity.py --tsv-dir /path/to/scrape
    python3 ocp-vlan-ip-capacity.py --self-test

Live output names the cluster you are logged into. Save it in a private
notes repo. Do not commit it here.
"""

from __future__ import print_function

import argparse
import ipaddress
import json
import os
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


def oc_json(args, required=True):
    result = oc_run(args + ["-o", "json"])
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip().splitlines()
        print("failed: oc {0}".format(" ".join(args)), file=sys.stderr)
        if err:
            print(err[-1], file=sys.stderr)
        if required:
            return None
        return {"items": []}
    return json.loads(result.stdout)


def parse_ip(text):
    try:
        return ipaddress.ip_address(text.split("%")[0])
    except ValueError:
        return None


def expand_spec(text):
    """Return the IPv4 addresses a pool spec owns. IPv6 is ignored here."""
    text = (text or "").strip()
    if not text:
        return set()
    if "-" in text and "/" not in text:
        left, right = text.split("-", 1)
        start = parse_ip(left.strip())
        end = parse_ip(right.strip())
        if start is None or end is None or start.version != 4 or end.version != 4:
            return set()
        if int(end) < int(start):
            return set()
        return {ipaddress.ip_address(n) for n in range(int(start), int(end) + 1)}
    try:
        net = ipaddress.ip_network(text, strict=False)
    except ValueError:
        return set()
    if net.version != 4:
        return set()
    return set(net)


def usable_hosts(net):
    """Node-subnet usable count. /31 and /32 follow the prefix size."""
    size = net.num_addresses
    if net.version == 4 and net.prefixlen <= 30:
        return size - 2
    return size


def vlan_of(iface):
    if not iface or "." not in iface:
        return None
    tail = iface.rsplit(".", 1)[-1]
    if tail.isdigit():
        return int(tail)
    return None


def empty_snapshot():
    return {
        "addresses": [],
        "routes": [],
        "pools": [],
        "service_ips": [],
        "egress_ips": [],
        "vmi_ips": [],
        "vips": [],
        "peers": [],
        "ads": [],
        "whereabouts": [],
        "br_ex_vlan": None,
        "who": "",
        "server": "",
    }


def add_ips(bucket, values):
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if not part or part.upper() == "PENDING":
                continue
            ip = parse_ip(part)
            if ip is not None and ip.version == 4:
                bucket.append(ip)


def load_oc():
    who = oc_text(["whoami"]) or "(whoami failed)"
    server = oc_text(["whoami", "--show-server"]) or "(server unknown)"
    nns = oc_json(["get", "nns"])
    pools = oc_json(["get", "ipaddresspool", "-A"])
    peers = oc_json(["get", "bgppeer", "-A"])
    ads = oc_json(["get", "bgpadvertisement", "-A"])
    svcs = oc_json(["get", "svc", "-A"])
    eips = oc_json(["get", "egressip", "-A"])
    if None in (nns, pools, peers, ads, svcs, eips):
        return None
    vmis = oc_json(["get", "vmi", "-A"], required=False)
    wps = oc_json(["get", "ippool.whereabouts.cni.cncf.io", "-A"], required=False)
    infra = oc_json(["get", "infrastructure", "cluster"], required=False)

    snap = empty_snapshot()
    snap["who"] = who
    snap["server"] = server
    bare_vlans = []
    for item in nns.get("items") or []:
        state = (item.get("status") or {}).get("currentState") or {}
        for iface in state.get("interfaces") or []:
            name = iface.get("name") or ""
            if name in ("lo", "ovn-k8s-mp0"):
                continue
            vlan = iface.get("vlan") or {}
            has_v4 = False
            block = iface.get("ipv4") or {}
            for addr in block.get("address") or []:
                ip = addr.get("ip")
                plen = addr.get("prefix-length")
                if not ip or plen is None:
                    continue
                has_v4 = True
                snap["addresses"].append({"iface": name, "ip": ip, "plen": int(plen)})
            if vlan.get("id") and not has_v4 and str(vlan.get("base-iface") or "").startswith("bond"):
                bare_vlans.append(int(vlan["id"]))
        for route in (state.get("routes") or {}).get("config") or []:
            snap["routes"].append(
                {
                    "iface": route.get("next-hop-interface") or "",
                    "nexthop": route.get("next-hop-address") or "",
                    "dest": route.get("destination") or "",
                }
            )
    if len(set(bare_vlans)) == 1:
        snap["br_ex_vlan"] = bare_vlans[0]

    for item in pools.get("items") or []:
        spec = item.get("spec") or {}
        snap["pools"].append(
            {
                "name": item["metadata"]["name"],
                "auto_assign": spec.get("autoAssign"),
                "addresses": list(spec.get("addresses") or []),
            }
        )
    for item in peers.get("items") or []:
        spec = item.get("spec") or {}
        snap["peers"].append(
            {
                "name": item["metadata"]["name"],
                "vrf": spec.get("vrf") or "",
                "addr": spec.get("peerAddress") or "",
            }
        )
    for item in ads.get("items") or []:
        spec = item.get("spec") or {}
        snap["ads"].append(
            {
                "pools": list(spec.get("ipAddressPools") or []),
                "peers": list(spec.get("peers") or []),
            }
        )
    for item in svcs.get("items") or []:
        spec = item.get("spec") or {}
        if spec.get("type") == "LoadBalancer":
            ingress = (item.get("status") or {}).get("loadBalancer", {}).get("ingress") or []
            for ing in ingress:
                if ing.get("ip"):
                    snap["service_ips"].append(ing["ip"])
        for ext in spec.get("externalIPs") or []:
            snap["service_ips"].append(ext)
    for item in eips.get("items") or []:
        for ip in (item.get("spec") or {}).get("egressIPs") or []:
            snap["egress_ips"].append(ip)
    for item in (vmis or {}).get("items") or []:
        for iface in (item.get("status") or {}).get("interfaces") or []:
            ips = list(iface.get("ipAddresses") or [])
            if iface.get("ipAddress"):
                ips.append(iface["ipAddress"])
            snap["vmi_ips"].extend(ips)
    if infra:
        bare = ((infra.get("status") or {}).get("platformStatus") or {}).get("baremetal") or {}
        for key in ("apiServerInternalIPs", "ingressIPs"):
            for ip in bare.get(key) or []:
                snap["vips"].append(ip)
        for key in ("apiServerInternalIP", "ingressIP"):
            if bare.get(key):
                snap["vips"].append(bare[key])
    for item in (wps or {}).get("items") or []:
        spec = item.get("spec") or {}
        allocs = spec.get("allocations") or {}
        ips = []
        if isinstance(allocs, dict):
            for key, val in allocs.items():
                if parse_ip(str(key)) is not None:
                    ips.append(str(key))
                elif isinstance(val, dict) and val.get("ip"):
                    ips.append(val["ip"])
        snap["whereabouts"].append({"range": spec.get("range") or "", "ips": ips})
    return snap


def _lines(path):
    if not os.path.isfile(path):
        return []
    with open(path) as handle:
        return [line.rstrip("\n") for line in handle if line.strip()]


def _fields(line):
    return line.split("\t")


def load_tsv(directory):
    snap = empty_snapshot()
    snap["who"] = "(snapshot)"
    snap["server"] = directory
    for line in _lines(os.path.join(directory, "nns-addresses.tsv")):
        parts = _fields(line)
        if len(parts) < 6 or parts[3] != "4":
            continue
        if parts[1] in ("lo", "ovn-k8s-mp0"):
            continue
        snap["addresses"].append({"iface": parts[1], "ip": parts[4], "plen": int(parts[5])})
    for line in _lines(os.path.join(directory, "gateways-control1.tsv")):
        parts = _fields(line)
        if len(parts) < 3:
            continue
        snap["routes"].append({"iface": parts[0], "nexthop": parts[1], "dest": parts[2]})
    for line in _lines(os.path.join(directory, "pools.tsv")):
        parts = _fields(line)
        if len(parts) < 3:
            continue
        auto = parts[1].split("=", 1)[-1]
        snap["pools"].append(
            {
                "name": parts[0],
                "auto_assign": auto,
                "addresses": [item for item in parts[2].split(",") if item],
            }
        )
    for line in _lines(os.path.join(directory, "lb-services.tsv")):
        parts = _fields(line)
        if len(parts) < 2:
            continue
        for ip in parts[1].split(","):
            if ip and ip.upper() != "PENDING":
                snap["service_ips"].append(ip)
    for line in _lines(os.path.join(directory, "external-ips.tsv")):
        parts = _fields(line)
        if len(parts) >= 3:
            for ip in parts[2].split(","):
                if ip:
                    snap["service_ips"].append(ip)
    for line in _lines(os.path.join(directory, "egressips.tsv")):
        parts = _fields(line)
        if len(parts) >= 2:
            for ip in parts[1].split(","):
                if ip:
                    snap["egress_ips"].append(ip)
    for line in _lines(os.path.join(directory, "vmi-ips.tsv")):
        parts = _fields(line)
        if not parts:
            continue
        for ip in parts[-1].split(","):
            if ip:
                snap["vmi_ips"].append(ip)
    for line in _lines(os.path.join(directory, "vips.tsv")):
        parts = _fields(line)
        if len(parts) < 2:
            continue
        for ip in parts[1].split(","):
            if ip:
                snap["vips"].append(ip)
    for line in _lines(os.path.join(directory, "bgp-peers.tsv")):
        parts = _fields(line)
        if len(parts) < 3:
            continue
        snap["peers"].append(
            {
                "name": parts[0],
                "vrf": parts[1].split("=", 1)[-1],
                "addr": parts[2].split("=", 1)[-1],
            }
        )
    for line in _lines(os.path.join(directory, "bgp-ads.tsv")):
        parts = _fields(line)
        pools = []
        peers = []
        for part in parts[1:]:
            if part.startswith("pools="):
                pools = [item for item in part.split("=", 1)[-1].split(",") if item]
            elif part.startswith("peers="):
                raw = part.split("=", 1)[-1]
                if raw and raw != "(all)":
                    peers = [item for item in raw.split(",") if item]
        snap["ads"].append({"pools": pools, "peers": peers})
    for line in _lines(os.path.join(directory, "ippools.tsv")):
        parts = _fields(line)
        rng = ""
        count = 0
        for part in parts:
            if part.startswith("range="):
                rng = part.split("=", 1)[-1]
            elif part.startswith("allocations="):
                try:
                    count = int(part.split("=", 1)[-1])
                except ValueError:
                    count = 0
        if count:
            print(
                "whereabouts pool {0} has {1} allocations and this TSV has no addresses".format(
                    rng or parts[0], count
                ),
                file=sys.stderr,
            )
        snap["whereabouts"].append({"range": rng, "ips": []})
    return snap


def _v4_list(values):
    found = []
    add_ips(found, values)
    return found


def _in_any_pool(ip, pools):
    for pool in pools:
        if ip in pool["set"]:
            return True
    return False


def build_report(snap):
    subnets = {}
    host_routes = []
    for addr in snap["addresses"]:
        ip = parse_ip(addr["ip"])
        if ip is None or ip.version != 4 or ip.is_loopback or ip.is_link_local:
            continue
        plen = int(addr["plen"])
        iface = addr["iface"]
        if plen >= 32:
            host_routes.append((iface, ip))
            continue
        net = ipaddress.ip_network("{0}/{1}".format(ip, plen), strict=False)
        rec = subnets.setdefault(
            net,
            {"iface": iface, "vlan": vlan_of(iface), "nodes": set()},
        )
        rec["nodes"].add(ip)
    for rec in subnets.values():
        if rec["iface"] == "br-ex" and rec["vlan"] is None and snap.get("br_ex_vlan"):
            rec["vlan"] = snap["br_ex_vlan"]

    gateways = {}
    for route in snap["routes"]:
        if route.get("dest") != "0.0.0.0/0":
            continue
        ip = parse_ip(route.get("nexthop") or "")
        if ip is None or ip.version != 4:
            continue
        gateways.setdefault(route["iface"], set()).add(ip)

    peers = []
    for peer in snap["peers"]:
        ip = parse_ip(peer.get("addr") or "")
        if ip is not None and ip.version != 4:
            ip = None
        peers.append({"name": peer["name"], "ip": ip, "vrf": peer.get("vrf") or ""})

    pools = []
    for pool in snap["pools"]:
        owned = set()
        for spec in pool["addresses"]:
            owned |= expand_spec(spec)
        if not owned:
            continue
        pools.append(
            {
                "name": pool["name"],
                "specs": list(pool["addresses"]),
                "set": owned,
                "peers": set(),
            }
        )
    by_name = {pool["name"]: pool for pool in pools}
    for ad in snap["ads"]:
        for name in ad["pools"]:
            pool = by_name.get(name)
            if pool is None:
                continue
            pool["peers"].update(ad["peers"])

    peer_by_name = {peer["name"]: peer for peer in peers}

    def subnet_for_ip(ip):
        if ip is None:
            return None
        for net in subnets:
            if ip in net:
                return net
        return None

    vrf_home = {}
    for peer in peers:
        home = subnet_for_ip(peer["ip"])
        if home is None or not peer["vrf"]:
            continue
        vrf_home.setdefault(peer["vrf"], set()).add(home)

    for pool in pools:
        homes = set()
        for name in pool["peers"]:
            peer = peer_by_name.get(name)
            if peer is None:
                continue
            home = subnet_for_ip(peer["ip"])
            if home is None and len(vrf_home.get(peer["vrf"], ())) == 1:
                home = next(iter(vrf_home[peer["vrf"]]))
            if home is not None:
                homes.add(home)
        pool["home"] = homes

    claimed = _v4_list(snap["service_ips"])
    claimed += _v4_list(snap["egress_ips"])
    claimed += _v4_list(snap["vmi_ips"])
    claimed += _v4_list(snap["vips"])
    for row in snap["whereabouts"]:
        claimed += _v4_list(row["ips"])
    for _iface, ip in host_routes:
        claimed.append(ip)

    def take(net, pool_set):
        found = set()
        for ip in claimed:
            if pool_set is not None:
                if ip in pool_set:
                    found.add(ip)
            elif ip in net and not _in_any_pool(ip, pools):
                found.add(ip)
        return found

    slices = []
    for net, rec in subnets.items():
        routers = set(gateways.get(rec["iface"], set()))
        for peer in peers:
            if peer["ip"] is not None and peer["ip"] in net:
                routers.add(peer["ip"])
        holds = set(rec["nodes"]) | take(net, None)
        occupied = holds | routers
        free = usable_hosts(net) - len(occupied)
        slices.append(
            {
                "kind": "node",
                "vlan": rec["vlan"],
                "iface": rec["iface"],
                "prefix": str(net),
                "size": usable_hosts(net),
                "holds": len(holds),
                "routers": len(routers),
                "free": free if routers else None,
                "name": "",
            }
        )

    unattached = []
    for pool in pools:
        used = take(None, pool["set"])
        size = len(pool["set"])
        row = {
            "kind": "pool",
            "prefix": ", ".join(pool["specs"]),
            "size": size,
            "holds": len(used),
            "routers": 0,
            "free": size - len(used),
            "name": pool["name"],
        }
        if len(pool["home"]) == 1:
            home = next(iter(pool["home"]))
            rec = subnets[home]
            row["vlan"] = rec["vlan"]
            row["iface"] = rec["iface"]
            slices.append(row)
        else:
            row["vlan"] = None
            row["iface"] = ""
            unattached.append(row)

    unplaced = []
    seen = set()
    for ip in _v4_list(snap["egress_ips"]) + _v4_list(snap["service_ips"]) + _v4_list(snap["vmi_ips"]):
        if ip in seen:
            continue
        seen.add(ip)
        if subnet_for_ip(ip) is None and not _in_any_pool(ip, pools):
            unplaced.append(str(ip))

    def sort_key(row):
        vlan = row["vlan"] if row["vlan"] is not None else 99999
        kind = 0 if row["kind"] == "node" else 1
        return (vlan, row["iface"], kind, row["prefix"])

    slices.sort(key=sort_key)
    unattached.sort(key=lambda row: row["name"])
    return {"slices": slices, "unattached": unattached, "unplaced": sorted(unplaced)}


def label(row):
    if row["vlan"] is not None:
        return str(row["vlan"])
    return row["iface"] or "-"


def render(snap, report):
    lines = []
    lines.append("# VLAN IPv4 address count")
    lines.append("")
    lines.append("User: {0}".format(snap.get("who") or ""))
    lines.append("Server: {0}".format(snap.get("server") or ""))
    lines.append("")
    lines.append("Node rows are usable hosts (network and broadcast removed).")
    lines.append("MetalLB rows count every address in the pool.")
    lines.append("A pool is listed on the VLAN of the BGP peers it is announced to.")
    lines.append("Free is blank when no gateway or BGP peer was seen on that subnet.")
    lines.append("")
    lines.append("| VLAN | Kind | Prefix | Size | OpenShift holds | Routers seen | Free |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for row in report["slices"]:
        free = "-" if row["free"] is None else str(row["free"])
        kind = "node" if row["kind"] == "node" else "metallb {0}".format(row["name"])
        lines.append(
            "| {0} | {1} | `{2}` | {3} | {4} | {5} | {6} |".format(
                label(row), kind, row["prefix"], row["size"], row["holds"], row["routers"], free
            )
        )
    if report["unattached"]:
        lines.append("")
        lines.append("## Pools with no peer on a node subnet")
        lines.append("")
        for row in report["unattached"]:
            lines.append(
                "- {0} `{1}` size {2}, holds {3}, free {4}".format(
                    row["name"], row["prefix"], row["size"], row["holds"], row["free"]
                )
            )
    if report["unplaced"]:
        lines.append("")
        lines.append("## Addresses not in a node subnet or a pool")
        lines.append("")
        for ip in report["unplaced"]:
            lines.append("- {0}".format(ip))
    lines.append("")
    return "\n".join(lines)


def self_test():
    snap = empty_snapshot()
    snap["who"] = "self-test"
    snap["server"] = "fixture"
    for host in ("192.0.2.7", "192.0.2.8", "192.0.2.9"):
        snap["addresses"].append({"iface": "br-ex", "ip": host, "plen": 24})
    snap["addresses"].append({"iface": "br-ex", "ip": "192.0.2.5", "plen": 32})
    snap["addresses"].append({"iface": "br-ex", "ip": "169.254.169.2", "plen": 29})
    snap["routes"].append({"iface": "br-ex", "nexthop": "192.0.2.1", "dest": "0.0.0.0/0"})
    snap["peers"] = [
        {"name": "a", "vrf": "", "addr": "192.0.2.2"},
        {"name": "b", "vrf": "", "addr": "192.0.2.3"},
    ]
    snap["pools"] = [
        {"name": "vip", "auto_assign": False, "addresses": ["192.0.2.128/25"]},
        {"name": "anycast", "auto_assign": False, "addresses": ["198.51.100.10/32"]},
        {"name": "lab", "auto_assign": False, "addresses": ["203.0.113.10-203.0.113.12"]},
    ]
    snap["ads"] = [
        {"pools": ["vip", "anycast"], "peers": ["a", "b"]},
        {"pools": ["missing"], "peers": ["no-such"]},
    ]
    snap["service_ips"] = ["192.0.2.128", "192.0.2.129", "192.0.2.129", "PENDING"]
    snap["vmi_ips"] = ["192.0.2.22", "10.1.0.5"]
    snap["egress_ips"] = ["203.0.113.50"]
    snap["vips"] = ["192.0.2.6"]
    report = build_report(snap)
    by_prefix = {row["prefix"]: row for row in report["slices"]}
    node = by_prefix["192.0.2.0/24"]
    pool = by_prefix["192.0.2.128/25"]
    anycast = by_prefix["198.51.100.10/32"]
    checks = [
        node["size"] == 254,
        node["holds"] == 6,
        node["routers"] == 3,
        node["free"] == 245,
        pool["size"] == 128,
        pool["holds"] == 2,
        pool["free"] == 126,
        pool["vlan"] == node["vlan"],
        anycast["holds"] == 0,
        anycast["size"] == 1,
        anycast["iface"] == "br-ex",
        len(report["unattached"]) == 1,
        report["unattached"][0]["size"] == 3,
        "10.1.0.5" in report["unplaced"],
        "203.0.113.50" in report["unplaced"],
        "169.254.169.2" not in report["unplaced"],
    ]
    # .6 is in vips, so holds are .5 .6 .7 .8 .9 .22 = 6, free = 254-3-6 = 245
    if node["holds"] != 6 or node["free"] != 245:
        print("self-test node {0}".format(node), file=sys.stderr)
        return 1
    if not all(checks):
        print(json.dumps(report, indent=2, default=str), file=sys.stderr)
        return 1
    print("self-test ok")
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description="Read-only VLAN and MetalLB IPv4 count.")
    parser.add_argument("--tsv-dir", help="Replay a saved scrape directory instead of oc.")
    parser.add_argument("--json", action="store_true", help="Print the count as JSON.")
    parser.add_argument("--self-test", action="store_true", help="Run the built-in fixture and exit.")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.tsv_dir:
        snap = load_tsv(args.tsv_dir)
    else:
        snap = load_oc()
        if snap is None:
            return 1
    report = build_report(snap)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render(snap, report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
