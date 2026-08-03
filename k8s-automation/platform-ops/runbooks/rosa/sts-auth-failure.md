---
title: "STS Authentication Failure"
platform: "rosa"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# STS Authentication Failure

## Symptom
Alert `ROSAOperatorCredentialRequestFailed` or `CloudCredentialInsufficient` fires. Cluster operators report `AccessDenied` or `InvalidIdentityToken` in logs. `oc get cloudcredential cluster` shows `Degraded=True`. AWS Console shows failed `AssumeRoleWithWebIdentity` calls from the cluster OIDC provider.

## Impact
Operators cannot reconcile AWS resources (ELB, EBS, Route53). New routes, volumes, and load balancers fail to provision. Existing workloads may degrade if credentials expire mid-operation.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check Cloud Credential Operator status
oc get clusteroperator cloud-credential
oc get cloudcredential cluster -o yaml

# 2. List CredentialRequests and their status
oc get credentialsrequests -A
oc get credentialsrequest <failing-cr> -n <namespace> -o yaml

# 3. Check CCO pod logs for STS errors
oc logs -n openshift-cloud-credential-operator deployment/cloud-credential-operator --tail=100 | grep -iE 'sts|denied|token'
```

## Common Causes

### Cause 1: IAM Role Trust Policy Mismatch
**Symptoms:** CloudTrail shows `AccessDenied` on `sts:AssumeRoleWithWebIdentity`; CCO logs reference `Not authorized to perform sts:AssumeRoleWithWebIdentity`; OIDC provider thumbprint or issuer URL mismatch after cluster rebuild
**Fix:**
```bash
# Get cluster OIDC issuer URL
oc get authentication cluster -o jsonpath='{.spec.serviceAccountIssuer}'

# Verify IAM role trust policy matches (via AWS CLI)
aws iam get-role --role-name <rosa-operator-role> --query 'Role.AssumeRolePolicyDocument'

# Update trust policy to include correct OIDC provider and service account subject
# Subject format: system:serviceaccount:<namespace>:<serviceaccount>
rosa describe cluster --cluster <cluster-name>  # confirm OIDC endpoint

# After IAM fix, restart CCO to re-reconcile
oc rollout restart deployment/cloud-credential-operator -n openshift-cloud-credential-operator
```

### Cause 2: Expired or Revoked Operator IAM Role Permissions
**Symptoms:** `AccessDenied` on specific AWS API calls (ec2, elasticloadbalancing); CredentialRequest status shows `Provisioned` but operator logs show permission errors; recent IAM policy change in change window
**Fix:**
```bash
# Identify which operator is failing
oc get clusteroperators | grep -i false
oc logs -n openshift-<operator-ns> deployment/<operator> --tail=50 | grep -i denied

# Check attached IAM policies for the operator role
aws iam list-attached-role-policies --role-name <operator-role>
aws iam simulate-principal-policy --policy-source-arn arn:aws:iam::<account>:role/<role> \
  --action-names ec2:DescribeInstances --resource-arns '*'

# Restore missing permissions via IAM policy update (requires change ticket)
# Force credential refresh
oc delete secret -n <operator-ns> <cloud-credentials-secret>
oc get credentialsrequest <cr-name> -n <operator-ns> -o yaml  # verify re-provisioned
```

## Escalation Criteria
Escalate to next level if:
- [ ] Multiple operators degraded due to credential failures
- [ ] IAM changes require AWS account admin approval
- [ ] OIDC provider needs recreation (cluster-level change)
- [ ] More than 30 minutes elapsed without progress — open Red Hat support case

## Related
- Skill: platform/rosa
- Skill: cloud/aws
- Runbook: runbooks/rosa/managed-addon-degraded.md
- Runbook: runbooks/ocp/operator-degraded.md
- Dashboard: Grafana → Platform / Cloud Credentials

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
