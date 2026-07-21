# ocp-net-metallb-report

Generates a **MetalLB** reference report (markdown) for an OpenShift cluster.

## Scope

**In scope**

| Section | Source |
|---|---|
| MetalLB Operator | `metallbs` (metallb-system) |
| BFD Profiles | `bfdprofiles` |
| BGP Peers | `bgppeers` (+ nodeSelectors) |
| IP Address Pools | `ipaddresspools` |
| BGP Advertisements | `bgpadvertisements` (+ nodeSelectors) |
| L2 Advertisements | `l2advertisements` |
| LoadBalancer Services | `svc` type=LoadBalancer (pool/IP anns, extTrafficPolicy, ports) |
| EgressServices | `egressservices` (k8s.ovn.org) — LB-tied egress |
| ServiceBGPStatus | summary counts only (noise control) |
| BGPSessionState | status roll-up only |
| FRR | FRRConfiguration / FRRNodeState counts |

**Out of scope**

- Host/node underlay → [`../ocp-net-core-report`](../ocp-net-core-report/)
- OVN EgressIP, Multus NAD/Whereabouts → **Extended Networking** (separate report)
- Combined core+MetalLB → [`../ocp-net-report`](../ocp-net-report/) (legacy combined; prefer the split scripts)

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Read access to `metallb-system` MetalLB CRs, cluster-wide Services,
  EgressServices, and FRR-K8s status CRDs when present

Read-only: only runs `oc get` / `oc whoami`.

## Usage

```bash
python3 ocp-net-metallb-report.py > metallb-<env>-<domain>-<site>.report.md
```

Example: `metallb-prod-nde-nn.report.md`.

## Review hints

- Advertisements referencing missing pools/peers are dangling.
- BGPAdvertisement `nodeSelectors` must align with EgressService / workload nodes.
- `<pending>` LoadBalancer services are often lab noise — confirm before documenting.
- EgressIP is **not** listed here; do not confuse with EgressService.

This script is generic (safe for public repos). Redirect live output to a
private notes repo.
