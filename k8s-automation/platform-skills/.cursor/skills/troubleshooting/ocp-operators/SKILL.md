---
name: troubleshooting/ocp-operators
description: >
  Use when diagnosing degraded OpenShift cluster operators.
  Covers ClusterOperator conditions, operator pods, and CSV failures.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: troubleshooting
refs:
  - core
  - platform/ocp
---

# Troubleshooting/OCP Operators

## When to Use
- `oc get co` shows `AVAILABLE=False` or `DEGRADED=True`
- Alert: `ClusterOperatorDown`, `ClusterOperatorDegraded`
- Operator pod crash-looping in `openshift-*` namespace
- OLM subscription or CSV not reaching `Succeeded`

## Key Concepts
- **ClusterOperator (CO)**: top-level health per platform component
- **OLM**: Operator Lifecycle Manager — manages CSV, Subscription, InstallPlan
- **CSV**: ClusterServiceVersion — operator install artifact; must be `Succeeded`
- **Interdependency**: some operators depend on others (e.g. ingress needs DNS)

## Commands and Patterns

```bash
# Operator overview
oc get co
oc get co [operator-name] -o yaml | grep -A15 "conditions:"

# Degraded operators only
oc get co -o json | jq -r '.items[] | select(.status.conditions[] | select(.type=="Degraded" and .status=="True")) | .metadata.name'

# Operator namespace pods
oc get pods -n openshift-[operator-name]
oc logs -n openshift-[operator-name] deployment/[operator] --tail=100

# OLM status
oc get csv -A | grep -v Succeeded
oc get subscription -A | grep -v "AtLatestKnown\|Installed"
oc get installplan -A

# Force reconcile (caution — ticket required)
oc delete pod -n openshift-[operator-name] -l name=[operator-name]-operator
```

## Common Issues

**CSV stuck in Installing / Failed**
- `oc describe csv [name] -n [namespace]` — read status.message
- Check operator pod logs and RBAC permissions
- Delete failed CSV and let OLM reinstall (non-prod first)

**CO Degraded — missing resources**
- Ingress without DNS: check `oc get dns cluster`
- Storage operator without default StorageClass

**Multiple operators degraded after upgrade**
- Check ClusterVersion: `oc get clusterversion`
- Wait for upgrade to complete; if stuck > 60 min see `platform/ocp` upgrade section
- Runbook: `platform-ops/runbooks/ocp/operator-degraded.md`

**Subscription not AtLatestKnown**
- `oc describe subscription [name] -n [namespace]`
- Check catalog source: `oc get catalogsource -A`

## References
- Platform: `platform/ocp`
- Runbook: `platform-ops/runbooks/ocp/operator-degraded.md`
- Onboarding issues: `tasks/client-onboarding` Step 5
