---
name: troubleshooting/acm-policies
description: >
  Use when diagnosing RHACM policy non-compliance or policy delivery failures.
  Covers Policy status, violations, and remediation.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: troubleshooting
refs:
  - core
  - acm/policies
  - acm/placement
---

# Troubleshooting/ACM Policies

## When to Use
- Policy shows `NonCompliant` on hub or managed cluster
- Alert: `PolicyViolation`, governance policy audit failure
- New cluster not receiving expected policies
- Client onboarding blocked at ACM step

## Key Concepts
- **Remediation**: `enforce` blocks non-compliant resources; `audit` reports only
- **PolicyReport**: on managed cluster — lists violations per resource
- **violation message**: human-readable reason in Policy status
- **Template policies**: use Gatekeeper/Kyverno constraints propagated via ACM

## Commands and Patterns

```bash
# Hub — policy compliance overview
oc get policies -n open-cluster-management \
  -o custom-columns=NAME:.metadata.name,COMPLIANT:.status.compliant,REMEDIATION:.spec.remediationAction

# Specific policy violations
oc get policy [policy-name] -n open-cluster-management -o yaml | grep -A30 "violations"

# Per-cluster compliance
oc get policy [policy-name] -n open-cluster-management \
  -o jsonpath='{range .status.statuses[*]}{.clusterName}{": "}{.compliant}{"\n"}{end}'

# Managed cluster — PolicyReport
oc config use-context [managed-cluster]
oc get policyreport -A
oc get policyreport -n [namespace] [report-name] -o yaml

# Kyverno (if used)
oc get clusterpolicy
oc get policyreport -n [namespace]
```

## Common Issues

**NonCompliant — missing required labels**
- Violation lists resources without `platform.io/*` labels
- Fix: add labels to deployment/service; see `core` naming conventions
- If intentional break-glass: annotate `platform.io/break-glass: INC-YYYY-NNN`

**NonCompliant — image tag `latest`**
- Production policy blocks `latest` tags
- Fix: pin to SHA or semver in Kustomize overlay
- See: `deploy/kustomize`

**Policy not on managed cluster**
- Placement not matching — see `acm/placement`
- ManagedCluster not Available on hub

**Enforce policy blocking deployment**
- Temporarily switch to audit (hub PR required — not break-glass for policies)
- Fix root cause in manifest; re-apply
- Runbook: `platform-ops/runbooks/acm/policy-noncompliant.md`

## References
- ACM skills: `acm/policies`, `acm/placement`
- Task: `tasks/policy-authoring`
- Runbook: `platform-ops/runbooks/acm/policy-noncompliant.md`
