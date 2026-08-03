---
title: "Prometheus Down"
platform: "all"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Prometheus Down

## Symptom
Alert `PrometheusDown`, `TargetDown`, or `Watchdog` (dead man's switch) stops firing — indicating the monitoring pipeline itself is broken. `oc get pods -n openshift-monitoring` shows `prometheus-k8s-*` pods not `Running`. Grafana dashboards show no data; Alertmanager stops routing alerts.

## Impact
The cluster is effectively blind — no metrics, no alerts, no SLO recording. Incidents may go undetected until client-reported. SLO error budgets cannot be calculated; compliance audit logging of observability may be violated.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check Prometheus and monitoring operator pods
oc get pods -n openshift-monitoring -l app.kubernetes.io/name=prometheus
oc get pods -n openshift-monitoring-operator

# 2. Check ClusterOperator monitoring status
oc get clusteroperator monitoring
oc describe clusteroperator monitoring

# 3. Review Prometheus pod logs and PVC status
oc logs -n openshift-monitoring prometheus-k8s-0 -c prometheus --tail=50
oc get pvc -n openshift-monitoring
```

## Common Causes

### Cause 1: Prometheus PVC Full or Corrupted
**Symptoms:** Prometheus pod in `CrashLoopBackOff`; logs show `no space left on device` or `opening storage failed`; PVC at 100% capacity; TSDB compaction errors
**Fix:**
```bash
# Check PVC usage
oc get pvc -n openshift-monitoring
oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- df -h /prometheus

# Reduce retention temporarily via cluster monitoring config
oc get configmap cluster-monitoring-config -n openshift-monitoring -o yaml
# Set spec.retention: 1d (change ticket required)

# If PVC corrupted, delete Prometheus pod (StatefulSet recreates) after freeing space
oc delete pod -n openshift-monitoring prometheus-k8s-0
oc get pods -n openshift-monitoring -l app.kubernetes.io/name=prometheus -w

# Plan PVC expansion or retention policy update post-incident
```

### Cause 2: Cluster Monitoring Operator Failure
**Symptoms:** `cluster-monitoring-operator` pod not running; Prometheus CR shows `ReconciliationFailed`; operator logs show RBAC or webhook errors; monitoring degraded after OCP upgrade
**Fix:**
```bash
# Check monitoring operator
oc get pods -n openshift-monitoring-operator
oc logs -n openshift-monitoring-operator deployment/cluster-monitoring-operator --tail=100

# Verify Prometheus CR and operator reconciliation
oc get prometheus k8s -n openshift-monitoring -o yaml | grep -A10 status

# Restart monitoring operator
oc rollout restart deployment/cluster-monitoring-operator -n openshift-monitoring-operator

# If RBAC issue, check SAR permissions
oc adm policy who-can create prometheuses.monitoring.coreos.com -n openshift-monitoring
```

## Escalation Criteria
Escalate to next level if:
- [ ] Prometheus does not recover after PVC remediation and operator restart
- [ ] Multiple monitoring components down (Alertmanager, Thanos, Telemeter)
- [ ] Production cluster blind for more than 15 minutes
- [ ] More than 30 minutes elapsed without progress

## Related
- Skill: observability/prometheus
- Skill: observability/platform-health
- Runbook: runbooks/observability/scrape-target-down.md
- Runbook: runbooks/observability/alertmanager-silenced.md
- Runbook: runbooks/ocp/operator-degraded.md
- Dashboard: Grafana → Monitoring / Prometheus Health

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
