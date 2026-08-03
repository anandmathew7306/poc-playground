---
name: acm/placement
description: >
  Use when configuring or troubleshooting RHACM Placement and PlacementDecision.
  Covers cluster selection, label selectors, and PolicySet binding.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: acm
refs:
  - core
  - acm/policies
---

# ACM/Placement

## When to Use
- New cluster not receiving policies or GitOps subscriptions
- Placement not matching expected managed clusters
- Configuring client-specific cluster targeting
- Client profile references `acm.placement: [name]`

## Key Concepts
- **Placement**: defines which ManagedClusters are selected via `spec.predicates`
- **PlacementDecision**: materialized result — lists matched cluster names
- **Label selectors**: match on `ManagedCluster` labels (e.g. `platform.io/client=acme`)
- **PlacementBinding**: links Placement to PolicySet or Subscription
- **Namespace**: Placements live in `open-cluster-management` or client namespace per convention

## Commands and Patterns

```bash
# Hub cluster
oc config use-context hub-prod

# List placements
oc get placement -n open-cluster-management
oc get placement [client]-placement -n open-cluster-management -o yaml

# PlacementDecision — which clusters matched
oc get placementdecision -n open-cluster-management
oc get placementdecision -l cluster.open-cluster-management.io/placement=[client]-placement -n open-cluster-management -o yaml

# ManagedCluster labels (must match placement predicates)
oc get managedcluster
oc get managedcluster [cluster-name] -o jsonpath='{.metadata.labels}' | jq .

# Add label to managed cluster if missing
oc label managedcluster [cluster-name] platform.io/client=[client]

# PlacementBinding
oc get placementbinding -n open-cluster-management | grep [client]
oc describe placementbinding [client]-binding -n open-cluster-management
```

## Common Issues

**Placement not matching any cluster**
- Compare Placement predicates to ManagedCluster labels
- `oc get placementdecision` empty = no match
- Common fix: add missing label to ManagedCluster import
- See: runbook `platform-ops/runbooks/acm/placement-not-matching.md`

**Cluster matched but policies not applied**
- PlacementBinding must reference correct PolicySet name
- Check Subscription channel for GitOps placements
- See: `acm/policies`

**Duplicate placements selecting same cluster**
- Two PolicySets on one cluster can conflict — consolidate per client
- Review `spec.numberOfClusters` if using spread scheduling

## References
- Config: `platform-config/acm/placements/`
- Policies: `acm/policies`
- Runbook: `platform-ops/runbooks/acm/placement-not-matching.md`
