---
name: platform/eks
description: >
  Use when working on Amazon EKS clusters.
  Covers node groups, add-ons, IRSA, and kubectl workflows.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: platform
refs:
  - core
  - cloud/aws
---

# Platform/EKS

## When to Use
- Amazon EKS managed Kubernetes clusters
- EKS add-on issues (EBS CSI, VPC CNI, CoreDNS)
- Node group scaling or NotReady nodes
- Client profile specifies `platform: eks`

## Key Concepts
- **Node groups**: EC2-backed or Fargate; managed via `aws eks` or cluster autoscaler
- **Add-ons**: AWS-managed components installed via EKS API
- **IRSA**: IAM Roles for Service Accounts via OIDC provider
- **CLI**: `kubectl` for workloads, `aws eks` for cluster lifecycle
- **No `oc`**: OCP-specific resources do not apply

## Commands and Patterns

```bash
# Cluster access
aws eks update-kubeconfig --name [cluster-name] --region [region]
kubectl cluster-info
kubectl get nodes -o wide

# Cluster and version
aws eks describe-cluster --name [cluster-name] --region [region]
kubectl version --short

# Node groups
aws eks list-nodegroups --cluster-name [cluster-name] --region [region]
aws eks describe-nodegroup --cluster-name [cluster-name] --nodegroup-name [ng] --region [region]

# Add-ons
aws eks list-addons --cluster-name [cluster-name] --region [region]
aws eks describe-addon --cluster-name [cluster-name] --addon-name aws-ebs-csi-driver --region [region]

# IRSA
aws eks describe-cluster --name [cluster-name] --query "cluster.identity.oidc.issuer"
kubectl get sa -n [namespace] [sa-name] -o yaml | grep role-arn

# Workloads
kubectl get pods -A --field-selector=status.phase!=Running
kubectl top nodes
```

## Common Issues

**Node NotReady**
- Check node group ASG events in AWS console
- CNI issues: `kubectl logs -n kube-system -l k8s-app=aws-node --tail=50`
- See: runbook `platform-ops/runbooks/eks/node-notready.md`

**Add-on Degraded**
- `aws eks describe-addon` for `health` field
- Common: EBS CSI missing IAM role, VPC CNI IP exhaustion
- Reconcile: `aws eks update-addon --resolve-conflicts OVERWRITE`
- See: runbook `platform-ops/runbooks/eks/addon-degraded.md`

**IRSA / permission denied**
- Verify trust policy on IAM role matches OIDC issuer + service account
- Annotation: `eks.amazonaws.com/role-arn` on ServiceAccount
- See: `cloud/aws`

**Pod scheduling failures**
- `kubectl describe pod [pod] -n [ns]` — check taints, resources, PVC
- Cluster autoscaler logs: `kubectl logs -n kube-system -l app=cluster-autoscaler`

## References
- Runbooks: `platform-ops/runbooks/eks/`
- Config base: `platform-config/base/eks/`
- Cloud: `cloud/aws`
