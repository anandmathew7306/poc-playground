# ocp-vlan-ip-capacity

Read-only IPv4 count of two kinds of range:

- A node subnet. Network and broadcast addresses are not usable. Gateways and BGP peer addresses are routers.
- A MetalLB pool. Every address in the range counts, including the ends of the prefix.

A pool is listed on the VLAN of the BGP peers it is announced to. The pool prefix does not have to be inside that VLAN's node subnet.

An address counts once. Several services on one LoadBalancer address are one hold. EgressService is not an extra address.

## Requirements

- `python3` (stdlib only)
- `oc` logged in to the cluster you want to check

Runs `oc get` and `oc whoami` only.

## Usage

```bash
python3 ocp-vlan-ip-capacity.py
python3 ocp-vlan-ip-capacity.py --self-test
python3 ocp-vlan-ip-capacity.py --tsv-dir /path/to/saved-scrape
```

`--tsv-dir` replays a directory of TSV files produced while checking a cluster by hand. The script does not fetch anything in that mode.

The script is generic. Live output names the cluster you are logged into. Save that output in a private notes repo. Do not commit live output here.
