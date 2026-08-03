---
title: "Cluster Operator Degraded"
platform: "ocp"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Cluster Operator Degraded

## Symptom
Alert `ClusterOperatorDegraded` or `ClusterOperatorDown` fires. `oc get clusteroperators` shows one or more operators with `DEGRADED=True` or `AVAILABLE=False`. ClusterVersion may show `Progressing=True` with a message referencing the failing operator.

## Impact
The degraded operator controls critical cluster functionality — networking, storage, monitoring, or authentication may be impaired. Dependent workloads fail health checks, upgrades stall, and new deployments may be blocked.

## Quick Checks
Run these first — in this order:

```bash
# 1. List degraded operators
oc get clusteroperators -o custom-columns=NAME:.metadata.name,DEGRADED:.status.conditions[?(@.type=="Degraded")].status,AVAILABLE:.status.conditions[?(@.type=="Available")].status,MESSAGE:.status.conditions[?(@.type=="Degraded")].message

# 2. Describe the failing operator
oc describe clusteroperator <operator-name>

# 3. Check operator pods and recent events
oc get pods -n openshift-<operator-namespace> -o wide
oc get events -n openshift-<operator-namespace> --sort-by='.lastTimestamp' | tail -20
```

## Common Causes

### Cause 1: Operator Pod CrashLoop or Image Pull Failure
**Symptoms:** Operator deployment pods in `CrashLoopBackOff` or `ImagePullBackOff`; events show `Back-off restarting` or `Failed to pull image`
**Fix:**
```bash
# Identify failing pods
oc get pods -n openshift-<operator-namespace> | grep -v Running

# Check pod logs and events
oc logs -n openshift-<operator-namespace> deployment/<operator-deployment> --tail=100
oc describe pod -n openshift-<operator-namespace> <pod-name>

# Force rollout restart after resolving image/registry issue
oc rollout restart deployment/<operator-deployment> -n openshift-<operator-namespace>
oc rollout status deployment/<operator-deployment> -n openshift-<operator-namespace>
```

### Cause 2: Operand Resource Stuck or Certificate Expired
**Symptoms:** Operator logs reference TLS handshake errors, webhook failures, or `operand not ready`; ClusterOperator message mentions webhook or CR reconciliation failure
**Fix:**
```bash
# Check operand CR status (example: ingress, DNS, monitoring)
oc get <operand-cr-type> -A
oc describe <operand-cr-type> <name> -n <namespace>

# Verify API server and webhook connectivity
oc get validatingwebhookconfigurations | grep <operator>
oc get mutatingwebhookconfigurations | grep <operator>

# Delete stuck operand pod to trigger reconciliation (only if safe)
oc delete pod -n openshift-<operator-namespace> -l app=<operator-label>

# If certificate-related, see sops/certificate-rotation.md
```

## Escalation Criteria
Escalate to next level if:
- [ ] Multiple operators degraded simultaneously (possible control plane issue)
- [ ] Operator remains degraded after pod restart and operand check
- [ ] Degraded operator blocks an in-progress cluster upgrade
- [ ] More than 45 minutes elapsed without progress

## Related
- Skill: troubleshooting/ocp-operators
- Skill: platform/ocp
- Runbook: runbooks/ocp/mco-stuck.md
- Runbook: runbooks/ocp/etcd-unhealthy.md
- SOP: sops/certificate-rotation.md
- Dashboard: Grafana → Platform / Cluster Operators

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
