---
name: cloud/aws
description: >
  Use when working with AWS resources for platform clusters.
  Covers IAM, STS, VPC, EC2, EBS, and AWS CLI patterns for PlatRel.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: cloud
refs:
  - core
---

# Cloud/AWS

## When to Use
- Any cluster on AWS (ROSA, ROSA HCP, EKS)
- IAM role, STS, or OIDC provider issues
- VPC, subnet, security group, or quota problems
- EBS volumes, load balancers, or Route53 for platform services

## Key Concepts
- **Accounts**: separate AWS accounts per client or environment where possible
- **STS**: short-lived credentials for ROSA; no static kubeconfig keys in Git
- **IRSA/OIDC**: EKS and ROSA use OIDC providers for pod-level IAM
- **Regions**: eu-west-1 (primary), eu-west-2 (DR), us-east-1 (select clients)
- **CLI**: `aws` with named profiles; never commit access keys

## Commands and Patterns

```bash
# Identity and region
aws sts get-caller-identity
export AWS_DEFAULT_REGION=eu-west-1

# IAM roles (ROSA/OSD pattern)
aws iam list-roles --query "Roles[?contains(RoleName,'OSD')].RoleName"
aws iam get-role --role-name [role-name]

# OIDC providers (IRSA/STS)
aws iam list-open-id-connect-providers

# EC2 / capacity
aws ec2 describe-instances --filters "Name=tag:kubernetes.io/cluster/[cluster],Values=owned"
aws service-quotas get-service-quota --service-code ec2 --quota-code L-1216C47A

# EBS volumes
aws ec2 describe-volumes --filters "Name=tag:kubernetes.io/cluster/[cluster],Values=owned"

# VPC and subnets
aws ec2 describe-subnets --filters "Name=tag:Name,Values=*[client]*"
aws ec2 describe-security-groups --group-ids [sg-id]

# EKS-specific
aws eks describe-cluster --name [cluster] --region eu-west-1
aws eks list-addons --cluster-name [cluster] --region eu-west-1

# CloudTrail for API errors (last hour)
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=RunInstances --max-results 10
```

## Common Issues

**VcpuLimitExceeded / InsufficientInstanceCapacity**
- Check quota: `aws service-quotas get-service-quota`
- Request increase via Service Quotas console
- Temporary: reduce NodePool/MachineSet replicas

**STS AssumeRoleWithWebIdentity failed**
- OIDC thumbprint mismatch — re-create provider if cluster rebuilt
- Trust policy `sub` claim must match service account
- See: `platform/rosa` runbook `sts-auth-failure.md`

**EBS volume attach failures**
- Verify CSI driver IAM role and `VolumeAttachment` events
- AZ mismatch: PVC and node must be same AZ

**ALB / ingress not provisioning**
- AWS Load Balancer Controller IAM policy
- Subnet tags: `kubernetes.io/role/elb` (public) or `internal-elb` (private)

## References
- Platform skills: `platform/rosa`, `platform/rosa-hcp`, `platform/eks`
- Config: `platform-config/clusters/*/cluster-info.yaml` (region field)
- Quotas: AWS Service Quotas console per account/region
