---
title: "ACM Hub Degraded"
platform: "acm"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# ACM Hub Degraded

## Symptom
Alert `ACMHubDegraded` or `MulticlusterHubDegraded` fires. `oc get multiclusterhub` shows `AVAILABLE=False` or `DEGRADED=True`. ACM console is unreachable or shows errors. Managed cluster registration, policy propagation, and GitOps sync stall across all spokes.

## Impact
All multi-cluster governance and deployment pipelines are impaired. Policies stop propagating, applications stop syncing, and new cluster imports fail. Every managed client cluster loses centralized control until the hub recovers.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check MultiClusterHub and operator status
oc get multiclusterhub -n open-cluster-management
oc get clusteroperators | grep -E 'multicluster|acm'

# 2. Check ACM component pods
oc get pods -n open-cluster-management
oc get pods -n open-cluster-management-hub

# 3. Review MCH operator logs and recent events
oc logs -n open-cluster-management deployment/multiclusterhub-operator --tail=100
oc get events -n open-cluster-management --sort-by='.lastTimestamp' | tail -20
```

## Common Causes

### Cause 1: ACM Operand Pod Failure or OOM
**Symptoms:** Key pods in `CrashLoopBackOff` — `governance-policy-propagator`, `cluster-manager`, `application-manager`; events show `OOMKilled` or `Back-off restarting`; hub degraded after upgrade or resource limit change
**Fix:**
```bash
# Identify failing pods
oc get pods -n open-cluster-management | grep -v Running
oc get pods -n open-cluster-management-hub | grep -v Running

# Check logs for the failing component
oc logs -n open-cluster-management deployment/<failing-deployment> --tail=100 --previous

# Restart the failing deployment
oc rollout restart deployment/<failing-deployment> -n open-cluster-management
oc rollout status deployment/<failing-deployment> -n open-cluster-management

# If OOM, increase resource limits via MultiClusterHub CR (change ticket required)
oc get multiclusterhub multiclusterhub -n open-cluster-management -o yaml
```

### Cause 2: Hub Cluster Control Plane or etcd Issue
**Symptoms:** Multiple ACM operators degraded simultaneously; API server latency high; underlying hub cluster operators (etcd, kube-apiserver) degraded; not isolated to a single ACM component
**Fix:**
```bash
# Check underlying hub cluster health first
oc get clusteroperators
oc get nodes
oc get etcd -o yaml

# If etcd or API server degraded, follow OCP runbooks first
# See: runbooks/ocp/etcd-unhealthy.md, runbooks/ocp/operator-degraded.md

# After control plane stabilizes, restart MCH reconciliation
oc annotate multiclusterhub multiclusterhub -n open-cluster-management \
  installer.open-cluster-management.io/mode=auto --overwrite

# Verify hub recovers
oc get multiclusterhub -n open-cluster-management -w
```

## Escalation Criteria
Escalate to next level if:
- [ ] Hub remains degraded after operand pod restart
- [ ] Underlying control plane (etcd/API) is degraded
- [ ] All managed clusters lose connectivity simultaneously
- [ ] More than 30 minutes elapsed without progress — page platform lead

## Related
- Skill: acm/policies
- Skill: acm/placement
- Skill: platform/ocp
- Runbook: runbooks/ocp/etcd-unhealthy.md
- Runbook: runbooks/ocp/operator-degraded.md
- Runbook: runbooks/acm/policy-noncompliant.md
- Dashboard: Grafana → ACM / Hub Health

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
