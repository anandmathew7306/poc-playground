---
title: "NodePool Unavailable"
platform: "rosa-hcp"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# NodePool Unavailable

## Symptom
Alert `HypershiftNodePoolUnavailable` or `NodePoolAvailable=False` fires. `oc get nodepool` shows `Available=False` with messages like `AsgInstanceLaunchFailures`, `InsufficientCapacity`, or `InstanceLimitExceeded`. Hosted cluster worker nodes drop below minimum; pods remain `Pending`.

## Impact
Worker capacity is insufficient to run workloads. Deployments, HPA scale-outs, and batch jobs fail to schedule. If all NodePools are unavailable, the hosted cluster effectively cannot serve compute workloads.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check NodePool status across hosted clusters
oc get nodepool -A
oc get nodepool <nodepool-name> -n clusters-<cluster-name> -o yaml | grep -A10 conditions

# 2. Describe NodePool for AWS launch failures
oc describe nodepool <nodepool-name> -n clusters-<cluster-name>

# 3. Check Hypershift operator and CAPI provider logs
oc logs -n hypershift deployment/operator --tail=100 | grep -i nodepool
oc logs -n capi-provider-aws-system deployment/capa-controller-manager --tail=50
```

## Common Causes

### Cause 1: AWS Instance Capacity or Subnet IP Exhaustion
**Symptoms:** NodePool conditions show `InsufficientInstanceCapacity` or `PrivateSubnetInsufficientIPAddresses`; ASG activities show launch failures; new instances stuck in `pending`
**Fix:**
```bash
# Check NodePool instance type and subnet configuration
oc get nodepool <nodepool-name> -n clusters-<cluster-name> -o jsonpath='{.spec.platform.aws}'

# Try alternate instance type (patch NodePool)
oc patch nodepool <nodepool-name> -n clusters-<cluster-name> --type=merge -p \
  '{"spec":{"platform":{"aws":{"instanceType":"m5.xlarge"}}}}'

# Verify subnet has available IPs in AWS console or CLI
aws ec2 describe-subnets --subnet-ids <subnet-id> --query 'Subnets[0].AvailableIpAddressCount'

# If subnet exhausted, add secondary CIDR or use alternate subnet (requires change ticket)
```

### Cause 2: IAM or Launch Template Misconfiguration
**Symptoms:** NodePool shows `InstanceProfileNotFound` or `UnauthorizedOperation`; CAPA logs show `AccessDenied` on `ec2:RunInstances`; recent IAM policy change
**Fix:**
```bash
# Check CAPA controller logs for permission errors
oc logs -n capi-provider-aws-system deployment/capa-controller-manager --tail=100 | grep -i denied

# Verify instance profile and role for NodePool
aws iam get-instance-profile --instance-profile-name <profile-name>

# Compare with working NodePool configuration
oc get nodepool -n clusters-<cluster-name> -o yaml

# Reconcile by deleting stuck Machine objects (CAPI will recreate)
oc get machines -n clusters-<cluster-name>
oc delete machine <stuck-machine-name> -n clusters-<cluster-name>
```

## Escalation Criteria
Escalate to next level if:
- [ ] All NodePools for a hosted cluster are unavailable
- [ ] AWS quota increase required and not approved within 15 minutes
- [ ] Subnet or VPC changes needed (network team involvement)
- [ ] More than 30 minutes elapsed without progress — escalate to Red Hat support

## Related
- Skill: platform/rosa-hcp
- Skill: cloud/aws
- Runbook: runbooks/rosa-hcp/hostedcluster-degraded.md
- Runbook: runbooks/rosa/sts-auth-failure.md
- Dashboard: https://grafana.example.com/d/acme

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
