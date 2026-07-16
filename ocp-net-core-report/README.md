# ocp-net-core-report

Generates a **core networking** reference report (markdown) for an OpenShift
cluster: cluster overview, nodes, NICs, bonds, OVS bridges, VLANs, VRFs and
routing.

Scope is host/node networking only. For MetalLB / load-balancer detail see
[`../ocp-net-metallb-report`](../ocp-net-metallb-report/); for a single
combined report see [`../ocp-net-report`](../ocp-net-report/).

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Read access to: nodes, `nns` (NodeNetworkState, from kubernetes-nmstate),
  and cluster config objects (`infrastructure`, `clusterversion`,
  `network.config`, `ingresses.config`)

Read-only: only runs `oc get` / `oc whoami`.

## Usage

```bash
# core networking report
python3 ocp-net-core-report.py > core-<cluster>.report.md

# include down/unused NICs and the geneve device
python3 ocp-net-core-report.py --all-nics
```

Suggested report naming: `core-<cluster>.report.md`.

## Report sections

| Section | Source | Notes |
|---|---|---|
| Cluster Overview | `infrastructure`, `clusterversion`, `network.config`, `ingresses.config` | name, version, CNI, pod/service CIDRs, API/Ingress VIPs, apps domain, topology |
| Node Inventory | `nodes` | roles, machine IPv4/IPv6 |
| Physical NIC Inventory | `nns` | up interfaces only unless `--all-nics` |
| Bond Detail | `nns` | mode, lacp_rate, miimon — watch for per-node drift |
| OVS Bridges | `nns` | bridge/port layout, OVN localnet networks, host IPs on OVS interfaces |
| Network Map | `nns` | one row per VLAN: subnet, VRF, gateway, routed vs L2-only |
| VLAN & Interface Detail | `nns` | per-node raw view backing the Network Map |
| VRF & Routing | `nns` | VRF → table ID → default gateway |

Reports are point-in-time snapshots (a generation timestamp is embedded in the
header). Values drift — regenerate rather than hand-editing values.
