---
title: "Policy Non-Compliant"
platform: "acm"
severity: "P2"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Policy Non-Compliant

## Symptom
Alert `PolicyNonCompliant` or `PolicyReportFailures` fires on the ACM hub. `oc get policies -n open-cluster-management` shows one or more policies with `Compliant=False`. Managed cluster policy status shows `NonCompliant` with violation details in the policy report.

## Impact
Governance guardrails are not enforced on affected clusters. Security baselines, configuration standards, or compliance requirements (e.g., SOC2 controls) are violated. Remediation policies may be blocked; audit findings may result if not resolved within SLA.

## Quick Checks
Run these first — in this order:

```bash
# 1. List non-compliant policies on the hub
oc get policies -n open-cluster-management -o custom-columns=NAME:.metadata.name,COMPLIANT:.status.compliant,CLUSTERS:.status.numberOfClusters.nonCompliant

# 2. Get violation details for the failing policy
oc get policy <policy-name> -n open-cluster-management -o yaml | grep -A30 status
oc get policyreport -A | grep <policy-name>

# 3. Check policy placement and managed cluster status
oc get placementdecisions -n open-cluster-management
oc get managedcluster <cluster-name> -o jsonpath='{.status.conditions}'
```

## Common Causes

### Cause 1: Resource Drift on Managed Cluster
**Symptoms:** Policy report lists specific resources violating the rule (e.g., missing label, privileged container, open NetworkPolicy); violation appeared after a recent deployment or manual change; only one cluster affected
**Fix:**
```bash
# View detailed violations on the managed cluster (switch context or use ACM console)
oc get policyreport -n <affected-namespace> -o yaml

# For enforce-mode policies, identify the violating resource
oc get <resource-type> <resource-name> -n <namespace> -o yaml

# Remediate the resource to match policy (preferred) or apply policy exception with ticket
oc label <resource-type> <resource-name> -n <namespace> platform.io/client=<client>
oc annotate <resource-type> <resource-name> -n <namespace> policy.open-cluster-management.io/override=enforce

# Verify compliance after fix (may take 1-2 reconciliation cycles)
oc get policy <policy-name> -n open-cluster-management -w
```

### Cause 2: Policy Misconfiguration or Incompatible Template
**Symptoms:** All targeted clusters show non-compliant; policy report shows template render errors or `unknown kind`; policy recently updated in platform-config; Kyvern/Gatekeeper constraint syntax error
**Fix:**
```bash
# Check policy definition and template
oc get policy <policy-name> -n open-cluster-management -o yaml
oc get configurationpolicy <policy-name> -n open-cluster-management -o yaml 2>/dev/null

# Review governance-policy-propagator logs
oc logs -n open-cluster-management deployment/governance-policy-propagator --tail=50

# Roll back policy to last known good version in platform-config
# After GitOps sync, verify policy re-propagates
oc get policies -n open-cluster-management | grep <policy-name>

# Test with audit mode before switching back to enforce
oc patch policy <policy-name> -n open-cluster-management --type=merge \
  -p '{"spec":{"remediationAction":"inform"}}'
```

## Escalation Criteria
Escalate to next level if:
- [ ] Security-critical policy (privileged containers, secret exposure) non-compliant in production
- [ ] Policy rollback does not restore compliance within 30 minutes
- [ ] Client requests policy exception requiring compliance team approval
- [ ] More than 4 hours elapsed for P2 without remediation plan

## Related
- Skill: troubleshooting/acm-policies
- Skill: acm/policies
- Runbook: runbooks/acm/placement-not-matching.md
- Runbook: runbooks/acm/hub-degraded.md
- Dashboard: Grafana → ACM / Policy Compliance

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
