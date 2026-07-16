# ocp-net-metallb-report

Generates a **MetalLB** reference report (markdown) for an OpenShift cluster:
BGP peers, IP address pools, BGP advertisements and LoadBalancer services.

Scope is MetalLB / load-balancer networking only. For host/node networking see
[`../ocp-net-core-report`](../ocp-net-core-report/); for a single combined
report see [`../ocp-net-report`](../ocp-net-report/).

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Read access to `bgppeers`, `ipaddresspools`, `bgpadvertisements` in
  `metallb-system`, and services cluster-wide

Read-only: only runs `oc get` / `oc whoami`.

## Usage

```bash
python3 ocp-net-metallb-report.py > metallb-<cluster>.report.md
```

Suggested report naming: `metallb-<cluster>.report.md`.

## Report sections

| Section | Source | Notes |
|---|---|---|
| BGP Peers | `bgppeers` (metallb-system) | peer address, ASNs, VRF, BFD profile — also documents upstream router adjacency |
| IP Address Pools | `ipaddresspools` (metallb-system) | address ranges, autoAssign, avoidBuggyIPs |
| BGP Advertisements | `bgpadvertisements` (metallb-system) | pool→peer mapping, aggregation length, localPref |
| LoadBalancer Services | `svc` (all namespaces) | assigned external IPs, `<pending>` if unassigned |

Useful cross-checks when reviewing a report:

- Advertisements referencing pools/peers that do not exist in the live lists
  are dangling (stale or copied config).
- `<pending>` LoadBalancer services have no IP assigned — verify whether they
  are in use or orphaned.

Reports are point-in-time snapshots (a generation timestamp is embedded in the
header). Values drift — regenerate rather than hand-editing values.
