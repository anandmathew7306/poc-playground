# ocp-net-report

Generates a **full network reference report** (markdown) for an OpenShift
cluster: core networking (cluster overview, nodes, NICs, bonds, OVS bridges,
VLANs, VRFs, routing) plus MetalLB (BGP peers, IP pools, advertisements,
LoadBalancer services).

For scoped reports see the sibling folders:

- [`../ocp-net-core-report`](../ocp-net-core-report/) — core networking only
- [`../ocp-net-metallb-report`](../ocp-net-metallb-report/) — MetalLB only

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Read access to: nodes, `nns` (NodeNetworkState, from kubernetes-nmstate),
  cluster config objects (`infrastructure`, `clusterversion`, `network.config`,
  `ingresses.config`), MetalLB CRs in `metallb-system`, and services
  cluster-wide

Read-only: only runs `oc get` / `oc whoami`.

## Usage

```bash
python3 ocp-net-report.py > <cluster>.report.md

# include down/unused NICs and the geneve device
python3 ocp-net-report.py --all-nics
```

## Report sections

Core networking: Cluster Overview, Node Inventory, Physical NIC Inventory,
Bond Detail, OVS Bridges, Network Map (one row per VLAN with subnet / VRF /
gateway / routed-vs-L2-only), VLAN & Interface Detail, VRF & Routing.

MetalLB: BGP Peers, IP Address Pools, BGP Advertisements, LoadBalancer
Services.

Section details are documented in the scoped folders' READMEs.

Reports are point-in-time snapshots (a generation timestamp is embedded in the
header). Values drift — regenerate rather than hand-editing values.
