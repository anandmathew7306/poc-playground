# ocp-net-extended-report

Generates an **Extended Networking** reference report (markdown) for an
OpenShift cluster.

## Scope

**In scope**

| Section | Source |
|---|---|
| EgressIP | `egressips` (k8s.ovn.org) |
| Egress-assignable nodes | node label `k8s.ovn.org/egress-assignable` (+ optional `egress-node`) |
| NetworkAttachmentDefinition | `network-attachment-definitions` (Multus NAD) |
| Whereabouts IPPools | `ippools.whereabouts.cni.cncf.io` |
| Related IPAM counts | OverlappingRangeIPReservation, NodeSlicePool, IPAMClaim |
| MultiNetworkPolicy | `multi-networkpolicies.k8s.cni.cncf.io` |

**Out of scope**

- Host/node underlay → [`../ocp-net-core-report`](../ocp-net-core-report/)
- MetalLB / EgressService → [`../ocp-net-metallb-report`](../ocp-net-metallb-report/)
- CRD inventory → [`../ocp-net-discovery`](../ocp-net-discovery/)

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Read access to the resources above

**Read-only:** only runs `oc get` / `oc whoami`. Never apply/patch/delete.

## Usage

```bash
python3 ocp-net-extended-report.py
python3 ocp-net-extended-report.py > extended-<env>-<domain>-<site>.report.md
```

Example: `extended-prod-nde-ek.report.md`.

Save live output that contains cluster identity into a **private** notes repo.
This directory is safe for public repos (generic script only).

## Review hints

- EgressIP status `IP@node` empty / unassigned → check egress-assignable labels.
- Explicit `k8s.ovn.org/egress-assignable=false` disables assignment (even if
  status looks stale).
- Do not confuse EgressIP with MetalLB **EgressService**.
