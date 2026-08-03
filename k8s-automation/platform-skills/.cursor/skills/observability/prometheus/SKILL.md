---
name: observability/prometheus
description: >
  Use when working with Prometheus, Alertmanager, and recording rules on platform clusters.
  Covers scrape config, PrometheusRule, and alert routing.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: observability
refs:
  - core
  - observability/platform-health
---

# Observability/Prometheus

## When to Use
- Prometheus or Alertmanager issues
- Creating SLO recording rules and alert rules
- Scrape target down alerts
- Client profile references `observability_skill: observability/prometheus`

## Key Concepts
- **Platform monitoring**: `openshift-monitoring` namespace (OCP/ROSA)
- **User workload monitoring**: enabled via `cluster-monitoring-config` ConfigMap
- **PrometheusRule**: CRD for recording and alerting rules
- **AlertmanagerConfig**: per-client alert routing (PagerDuty, Slack)
- **SLO rules**: defined in `platform-config/slos/[client].yaml`, deployed as PrometheusRule

## Commands and Patterns

```bash
# Prometheus status (OCP/ROSA)
oc get prometheus -n openshift-monitoring
oc get prometheusrule -n openshift-monitoring
oc get prometheusrule -A | grep [client]

# User workload monitoring
oc get configmap cluster-monitoring-config -n openshift-monitoring -o yaml

# Alertmanager
oc get alertmanager -n openshift-monitoring
oc get alertmanagerconfig -A | grep [client]

# Scrape targets (port-forward)
oc port-forward -n openshift-monitoring prometheus-k8s-0 9090:9090
# Browse http://localhost:9090/targets

# Test PromQL
oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- \
  promtool query instant http://localhost:9090 'up{job="api-gateway"}'

# EKS equivalent
kubectl get prometheusrule -A
kubectl get servicemonitor -A
```

## Common Issues

**Scrape target down**
- Check ServiceMonitor/PodMonitor labels match Prometheus selector
- NetworkPolicy blocking scrape port
- See: runbook `platform-ops/runbooks/observability/scrape-target-down.md`

**Alerts not reaching PagerDuty**
- Verify AlertmanagerConfig receiver and route matchers
- Test: `amtool alert add alertname=test client=[client]`
- See: runbook `platform-ops/runbooks/observability/alertmanager-silenced.md`

**SLO recording rule not producing metrics**
- `oc get prometheusrule [client]-slo -o yaml` — check PromQL syntax
- Compare to `platform-config/slos/[client].yaml` indicator definitions

**Prometheus down / crashloop**
- Check PVC storage and memory limits
- See: runbook `platform-ops/runbooks/observability/prometheus-down.md`

## References
- SLO definitions: `platform-config/slos/`
- Health checks: `observability/platform-health`
- Runbooks: `platform-ops/runbooks/observability/`
