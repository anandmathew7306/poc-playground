---
title: "HostedCluster Degraded"
platform: "rosa-hcp"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# HostedCluster Degraded

## Symptom
The HostedCluster resource shows `status.conditions` with `type=Degraded` and `status=True`. Alerts may fire as `HypershiftHostedClusterDegraded` or `ROSAHostedClusterUnhealthy`. The management cluster reports the hosted control plane or worker nodes are not fully operational.

## Impact
Acme production workloads on the hosted cluster may experience API unavailability, failed deployments, or pod scheduling failures. SOC2 availability SLO is at risk if not resolved within 30 minutes.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check HostedCluster status
oc get hostedcluster -n clusters-acme-prod

# 2. Describe HostedCluster for conditions and events
oc describe hostedcluster acme-prod -n clusters-acme-prod

# 3. Check NodePool status
oc get nodepool -n clusters-acme-prod
oc describe nodepool acme-prod-workers -n clusters-acme-prod
```

## Common Causes

### Cause 1: NodePool Capacity Issue
**Symptoms:** NodePool shows `Available=False`, instances failing to launch, or insufficient nodes for workload scheduling
**Fix:**
```bash
# Check NodePool conditions
oc get nodepool acme-prod-workers -n clusters-acme-prod -o yaml | grep -A5 conditions

# Scale NodePool if at minimum and workloads are pending
oc patch nodepool acme-prod-workers -n clusters-acme-prod --type=merge -p '{"spec":{"replicas":3}}'

# Check AWS Auto Scaling Group events in eu-west-1 console
```

### Cause 2: AWS Quota Exceeded
**Symptoms:** NodePool events show `InsufficientInstanceCapacity` or `VcpuLimitExceeded`, new nodes fail to provision
**Fix:**
```bash
# Verify quota errors in hypershift operator logs
oc logs -n hypershift deployment/operator --tail=100 | grep -i quota

# Request quota increase via AWS Service Quotas console (eu-west-1)
# Temporary mitigation: reduce NodePool replicas to fit within quota
oc patch nodepool acme-prod-workers -n clusters-acme-prod --type=merge -p '{"spec":{"replicas":2}}'
```

## Escalation Criteria
Escalate to next level if:
- [ ] HostedCluster remains Degraded after NodePool remediation
- [ ] AWS quota increase required and not approved within 15 minutes
- [ ] More than 30 minutes elapsed without progress — escalate to Red Hat support with case reference ACME-[ticket]

## Related
- Skill: platform/rosa-hcp
- Runbook: runbooks/rosa-hcp/nodepool-unavailable.md
- Dashboard: https://grafana.example.com/d/acme

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-01 | platrel | Initial version with Acme-specific context |
| 2026-06-13 | platrel | Updated escalation links and cross-references |
