---
title: "Alertmanager Silenced"
platform: "all"
severity: "P2"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Alertmanager Silenced

## Symptom
Expected alerts stop firing but the underlying condition persists. Alertmanager UI shows active silences matching production alert names. On-call reports missing pages during an active incident. `amtool` or API shows silences created without expiry or with wildcard matchers.

## Impact
Critical alerts are suppressed — incidents go undetected, MTTR increases, and SLO breaches may occur without paging. Silences intended for maintenance may have been left in place or created with overly broad matchers affecting unrelated alerts.

## Quick Checks
Run these first — in this order:

```bash
# 1. List active silences in Alertmanager
oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- \
  amtool silence query

# 2. Check Alertmanager routes and receivers
oc get secret alertmanager-main -n openshift-monitoring -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d

# 3. Verify alerts are firing in Prometheus but not reaching Alertmanager
oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- \
  promtool query instant 'ALERTS{alertstate="firing"}' | head -20
```

## Common Causes

### Cause 1: Stale Maintenance Silence Not Expired
**Symptoms:** Silence created during a maintenance window still active; silence comment references a past change ticket; `endsAt` timestamp in the past but silence still listed (bug) or set to far-future date
**Fix:**
```bash
# List silences with details
oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- \
  amtool silence query -o json | jq '.[] | {id: .id, comment: .comment, endsAt: .endsAt, matchers: .matchers}'

# Expire a specific silence by ID
oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- \
  amtool silence expire <silence-id>

# Verify alerts resume routing
oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- \
  amtool alert query

# Document in incident ticket and notify on-call channel
```

### Cause 2: Overly Broad Silence Matchers
**Symptoms:** Silence uses regex or `alertname=~".*"` matcher suppressing many alerts; silence created during incident triage to reduce noise; unrelated services stop alerting
**Fix:**
```bash
# Identify broad silences
oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- \
  amtool silence query -o json | jq '.[] | select(.matchers[].value | test("\\.|\\*|~"))'

# Expire the broad silence
oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- \
  amtool silence expire <silence-id>

# Recreate targeted silence if still needed (narrow matchers only)
oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- \
  amtool silence add alertname=KubeNodeNotReady cluster=<cluster-name> \
  --comment="Maintenance: node drain INC-2026-XXX" --duration=2h

# Update team SOP: silences require ticket reference and max 4h duration
```

## Escalation Criteria
Escalate to next level if:
- [ ] Cannot determine who created the silence or when
- [ ] Expiring silences does not restore alert routing
- [ ] Production has been without paging for more than 60 minutes
- [ ] Alertmanager itself is down — see runbooks/observability/prometheus-down.md

## Related
- Skill: observability/prometheus
- Skill: tasks/incident-response
- Runbook: runbooks/observability/prometheus-down.md
- Runbook: runbooks/observability/scrape-target-down.md
- Dashboard: Grafana → Monitoring / Alertmanager

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
