---
title: "EKS Add-on Degraded"
platform: "eks"
severity: "P2"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# EKS Add-on Degraded

## Symptom
Alert `EKSAddonDegraded` fires or `aws eks describe-addon` shows `status=DEGRADED` or `status=CREATE_FAILED`. In-cluster, add-on pods (e.g., `aws-node`, `kube-proxy`, `coredns`, `aws-ebs-csi-driver`) are not healthy. Workloads report storage mount failures or DNS resolution errors.

## Impact
Core cluster services provided by the add-on are impaired. Common failures: pod networking (VPC CNI), DNS (CoreDNS), storage (EBS CSI), or service proxy (kube-proxy). Application deployments and scaling are blocked.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check EKS add-on status via AWS CLI
aws eks list-addons --cluster-name <cluster-name>
aws eks describe-addon --cluster-name <cluster-name> --addon-name <addon-name>

# 2. Check add-on pods in kube-system or dedicated namespace
kubectl get pods -n kube-system -l app.kubernetes.io/name=<addon-name>
kubectl get pods -n kube-system | grep -E 'aws-node|coredns|kube-proxy|ebs-csi'

# 3. Review add-on pod logs and events
kubectl logs -n kube-system -l k8s-app=<addon-label> --tail=50
kubectl get events -n kube-system --sort-by='.lastTimestamp' | tail -20
```

## Common Causes

### Cause 1: Add-on Version Incompatible with Kubernetes Version
**Symptoms:** `describe-addon` shows `CREATE_FAILED` with version conflict; add-on pods crash with `unsupported Kubernetes version`; cluster upgrade recently completed
**Fix:**
```bash
# Check cluster and add-on versions
aws eks describe-cluster --name <cluster-name> --query 'cluster.version'
aws eks describe-addon --cluster-name <cluster-name> --addon-name <addon-name> \
  --query 'addon.{version:addonVersion,status:status}'

# Update add-on to compatible version
aws eks update-addon --cluster-name <cluster-name> --addon-name <addon-name> \
  --addon-version <compatible-version> --resolve-conflicts OVERWRITE

# Verify add-on becomes ACTIVE
aws eks describe-addon --cluster-name <cluster-name> --addon-name <addon-name> \
  --query 'addon.status'
kubectl get pods -n kube-system -l k8s-app=<addon-label> -w
```

### Cause 2: IAM Role or IRSA Misconfiguration
**Symptoms:** EBS CSI or other IRSA-enabled add-on logs show `AccessDenied`; service account missing `eks.amazonaws.com/role-arn` annotation; OIDC provider not associated with cluster
**Fix:**
```bash
# Check service account IRSA annotation
kubectl get sa -n kube-system <addon-sa> -o jsonpath='{.metadata.annotations}'

# Verify OIDC provider exists for cluster
aws eks describe-cluster --name <cluster-name> --query 'cluster.identity.oidc.issuer'
aws iam list-open-id-connect-providers

# Recreate add-on with correct service account role
aws eks delete-addon --cluster-name <cluster-name> --addon-name <addon-name>
aws eks create-addon --cluster-name <cluster-name> --addon-name <addon-name> \
  --service-account-role-arn arn:aws:iam::<account>:role/<addon-irsa-role>

# Confirm pods start and credentials work
kubectl logs -n kube-system -l app=ebs-csi-controller --tail=30
```

## Escalation Criteria
Escalate to next level if:
- [ ] Core add-ons (vpc-cni, coredns, kube-proxy) are degraded
- [ ] Add-on update fails twice with `CREATE_FAILED`
- [ ] IRSA role recreation requires IAM admin approval
- [ ] More than 45 minutes elapsed without progress

## Related
- Skill: platform/eks
- Skill: cloud/aws
- Runbook: runbooks/eks/node-notready.md
- Runbook: runbooks/rosa/sts-auth-failure.md
- Dashboard: Grafana → EKS / Add-ons

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
