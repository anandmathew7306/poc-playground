---
title: "Placement Not Matching"
platform: "acm"
severity: "P2"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Placement Not Matching

## Symptom
Alert `PlacementNoClustersMatched` or `PlacementDecisionEmpty` fires. `oc get placementdecisions` shows zero matched clusters or `numberOfSelectedClusters=0`. Policies, applications, or subscriptions bound to the Placement are not deployed to expected managed clusters.

## Impact
GitOps applications, governance policies, and configuration bundles do not reach target clusters. New clusters may not receive baseline configuration. Client workloads on affected clusters operate without required guardrails.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check Placement and PlacementDecision status
oc get placement -n open-cluster-management
oc get placementdecision -n open-cluster-management
oc describe placement <placement-name> -n open-cluster-management

# 2. Verify managed cluster labels match Placement predicates
oc get managedclusters -o custom-columns=NAME:.metadata.name,LABELS:.metadata.labels
oc get placement <placement-name> -n open-cluster-management -o yaml | grep -A20 predicates

# 3. Check placement controller logs
oc logs -n open-cluster-management deployment/cluster-manager-placement-controller --tail=50
```

## Common Causes

### Cause 1: Managed Cluster Missing Required Labels
**Symptoms:** PlacementDecision shows `numberOfSelectedClusters: 0`; managed cluster exists but lacks labels referenced in Placement predicates (e.g., `environment=prod`, `platform.io/client=acme`); cluster recently imported without label sync
**Fix:**
```bash
# Compare Placement predicates with cluster labels
oc get placement <placement-name> -n open-cluster-management -o jsonpath='{.spec.predicates}'
oc get managedcluster <cluster-name> --show-labels

# Add missing labels to the managed cluster
oc label managedcluster <cluster-name> environment=prod platform.io/client=<client>

# Verify PlacementDecision updates (may take 30-60 seconds)
oc get placementdecision -n open-cluster-management -l cluster.open-cluster-management.io/placement=<placement-name>

# Confirm bound policies show the cluster as a target
oc get policy <policy-name> -n open-cluster-management -o yaml | grep -A5 status
```

### Cause 2: Cluster Not Joined or Klusterlet Unhealthy
**Symptoms:** Managed cluster shows `ManagedClusterConditionAvailable=False`; klusterlet pods not running on spoke; Placement cannot select cluster even with correct labels; recent cluster import or certificate rotation
**Fix:**
```bash
# Check managed cluster conditions on hub
oc get managedcluster <cluster-name> -o yaml | grep -A5 conditions

# On the spoke cluster, verify klusterlet health
oc get pods -n open-cluster-management-agent
oc get klusterlet -o yaml

# Check registration operator logs on hub
oc logs -n open-cluster-management deployment/cluster-manager-registration-controller --tail=50

# If klusterlet unhealthy, restart registration pods on spoke
oc delete pod -n open-cluster-management-agent -l app=klusterlet-registration-agent
oc delete pod -n open-cluster-management-agent -l app=klusterlet-work-agent

# Re-import if cluster is stale (requires change ticket and client notification)
```

## Escalation Criteria
Escalate to next level if:
- [ ] Production cluster not receiving policies due to placement failure
- [ ] Klusterlet restart does not restore cluster availability within 30 minutes
- [ ] Multiple placements fail simultaneously (possible hub issue)
- [ ] More than 60 minutes elapsed without progress

## Related
- Skill: acm/placement
- Skill: troubleshooting/acm-policies
- Runbook: runbooks/acm/policy-noncompliant.md
- Runbook: runbooks/acm/hub-degraded.md
- Dashboard: Grafana → ACM / Placements

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
