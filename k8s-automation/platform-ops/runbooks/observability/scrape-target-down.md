---
title: "Scrape Target Down"
platform: "all"
severity: "P2"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Scrape Target Down

## Symptom
Alert `TargetDown` fires with labels identifying a specific `job`, `namespace`, or `service`. Prometheus targets page shows `DOWN` with scrape errors like `connection refused`, `context deadline exceeded`, or `401 Unauthorized`. Grafana panels for the affected service show gaps.

## Impact
Metrics for the affected service are missing — dashboards incomplete, SLO recording rules may produce false results, and alerts depending on those metrics will not fire. Blind spots in observability during the outage window.

## Quick Checks
Run these first — in this order:

```bash
# 1. Identify down targets in Prometheus
oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- \
  promtool query instant 'up{job="<job-name>"} == 0'

# 2. Check ServiceMonitor or PodMonitor configuration
oc get servicemonitor -n <namespace>
oc get servicemonitor <name> -n <namespace> -o yaml

# 3. Verify target pods and service endpoints exist
oc get pods -n <namespace> -l <app-label>
oc get endpoints -n <namespace> <service-name>
oc get svc -n <namespace> <service-name> -o yaml
```

## Common Causes

### Cause 1: Target Pod Not Running or Missing Metrics Endpoint
**Symptoms:** `up{job="..."} == 0`; scrape error `connection refused` on port; target pods in `CrashLoopBackOff` or scaled to zero; `/metrics` path returns 404
**Fix:**
```bash
# Check target pod health
oc get pods -n <namespace> -l app=<app-label>
oc logs -n <namespace> deployment/<app-deployment> --tail=50

# Verify metrics endpoint responds
oc run curl-test --image=curlimages/curl --rm -it --restart=Never -- \
  curl -s http://<service>.<namespace>.svc:8080/metrics | head -5

# Fix the application or scale up if HPA scaled to zero
oc scale deployment/<app-deployment> -n <namespace> --replicas=2

# Confirm target recovers in Prometheus
oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- \
  promtool query instant 'up{job="<job-name>"}'
```

### Cause 2: ServiceMonitor Misconfiguration or Network Policy Block
**Symptoms:** Scrape error `context deadline exceeded` or `no such host`; ServiceMonitor port/name mismatch; NetworkPolicy blocks openshift-monitoring namespace; TLS verification failure
**Fix:**
```bash
# Compare ServiceMonitor spec with actual service ports
oc get servicemonitor <name> -n <namespace> -o yaml
oc get svc <service-name> -n <namespace> -o jsonpath='{.spec.ports}'

# Check NetworkPolicy allows monitoring namespace
oc get networkpolicy -n <namespace>
oc describe networkpolicy <policy-name> -n <namespace>

# Allow Prometheus scraper (if default-deny policy)
# Add ingress rule for namespace openshift-monitoring label

# Fix ServiceMonitor port or path
oc patch servicemonitor <name> -n <namespace> --type=merge \
  -p '{"spec":{"endpoints":[{"port":"metrics","path":"/metrics"}]}}'

# Reload Prometheus config (operator handles automatically)
oc get pods -n openshift-monitoring -l app.kubernetes.io/name=prometheus -w
```

## Escalation Criteria
Escalate to next level if:
- [ ] More than 10 targets down simultaneously (possible Prometheus or network issue)
- [ ] ServiceMonitor fix does not restore scraping within 30 minutes
- [ ] Affects SLO recording rules for a production client
- [ ] More than 60 minutes elapsed without progress

## Related
- Skill: observability/prometheus
- Skill: observability/platform-health
- Runbook: runbooks/observability/prometheus-down.md
- Runbook: runbooks/network/ovn-pod-connectivity.md
- Dashboard: Grafana → Monitoring / Scrape Targets

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
