---
title: "Managed Add-on Degraded"
platform: "rosa"
severity: "P2"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Managed Add-on Degraded

## Symptom
Alert `ROSAAddonDegraded` fires or `rosa list addons` shows an add-on in `degraded` state. In-cluster, the add-on operator pod is not `Running` or the add-on CR reports `Degraded=True`. Common add-ons: `aws-ebs-csi-driver`, `aws-load-balancer-controller`, `managed-odf`, `openshift-gitops`.

## Impact
Platform capabilities provided by the add-on are unavailable — storage provisioning, ingress/load balancing, or GitOps sync may fail. Dependent application deployments stall or enter crash loops.

## Quick Checks
Run these first — in this order:

```bash
# 1. List add-on status via ROSA CLI
rosa list addons --cluster <cluster-name>

# 2. Check add-on operator in cluster
oc get pods -n openshift-<addon-namespace>
oc get clusteroperator | grep -i <addon-related-operator>

# 3. Review add-on installation status and events
oc get addon <addon-name> -n openshift-<addon-namespace> -o yaml 2>/dev/null || \
  oc describe deployment -n openshift-<addon-namespace>
oc get events -n openshift-<addon-namespace> --sort-by='.lastTimestamp' | tail -20
```

## Common Causes

### Cause 1: Add-on Version Incompatible with Cluster Version
**Symptoms:** Add-on install or upgrade failed; operator logs show `unsupported OCP version`; `rosa list addons` shows `installing` stuck for >15 minutes
**Fix:**
```bash
# Check cluster and add-on versions
oc get clusterversion
rosa list addons --cluster <cluster-name> --output json | jq '.[] | select(.id=="<addon-id>")'

# Install compatible add-on version via ROSA
rosa install addon --cluster <cluster-name> <addon-id> --version <compatible-version>

# Verify installation completes
rosa list addons --cluster <cluster-name>
oc get pods -n openshift-<addon-namespace> -w
```

### Cause 2: AWS IAM Permissions Missing for Add-on
**Symptoms:** Add-on operator logs show `AccessDenied` on AWS API calls; CSI driver cannot create volumes; ALB controller cannot describe VPC; STS credential request failed
**Fix:**
```bash
# Check operator logs for AWS errors
oc logs -n openshift-<addon-namespace> deployment/<addon-operator> --tail=100

# Verify ROSA add-on IAM roles exist
aws iam list-roles | grep <cluster-id>-<addon>

# Reinstall add-on to recreate IAM roles (maintenance window)
rosa uninstall addon --cluster <cluster-name> <addon-id>
rosa install addon --cluster <cluster-name> <addon-id>

# Confirm credentials provisioned
oc get credentialsrequests -A | grep <addon>
```

## Escalation Criteria
Escalate to next level if:
- [ ] Add-on reinstall fails twice
- [ ] Degraded add-on blocks production workload deployment
- [ ] IAM role recreation requires AWS org-level approval
- [ ] More than 45 minutes elapsed without progress

## Related
- Skill: platform/rosa
- Skill: cloud/aws
- Runbook: runbooks/rosa/sts-auth-failure.md
- Runbook: runbooks/ocp/operator-degraded.md
- Dashboard: Grafana → Platform / Add-ons

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
