# ocp-net-discovery

Read-only **inventory** of networking-related CRDs (and a few built-in
resources) on an OpenShift cluster.

Use this before extending `ocp-net-core-report` / `ocp-net-metallb-report`, so
documentation and scripts cover what actually exists (and skip empty noise).

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Permission to list CRDs and get the filtered resource kinds

Read-only: only runs `oc get` / `oc whoami`.

## Usage

```bash
python3 ocp-net-discovery.py
python3 ocp-net-discovery.py > discovery-<cluster>.md
```

Suggested: save output that contains cluster identity into a **private**
notes repo. This directory is safe for public repos (generic script only).

## What it does

1. Lists CRDs whose name or API group matches networking keywords
   (metallb, ovn, egress, nmstate, cni, sriov, …).
2. Counts live objects per matching CRD.
3. Suggests a documentation/script **home** (heuristic): `metallb`,
   `metallb-adjacent`, `core (ovn/policy)`, `core (host/cni)`,
   `core (cluster-config)`, or `review`.
4. Prints convenience counts for LoadBalancer Services, NetworkPolicies,
   EgressIPs, and EgressServices.

## Related scripts

- [`../ocp-net-core-report`](../ocp-net-core-report/) — host/node networking
- [`../ocp-net-metallb-report`](../ocp-net-metallb-report/) — MetalLB
- [`../ocp-net-report`](../ocp-net-report/) — combined core + MetalLB
