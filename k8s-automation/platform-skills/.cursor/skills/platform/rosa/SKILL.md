---
name: platform/rosa
description: >
  Use when working on Red Hat OpenShift Service on AWS (classic ROSA, non-HCP).
  Covers STS authentication, managed add-ons, and ROSA CLI workflows.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: platform
refs:
  - core
  - cloud/aws
---

# Platform/ROSA

## When to Use
- Classic ROSA clusters (not Hypershift/HCP)
- STS/IAM role authentication issues
- ROSA managed add-on failures (e.g. logging, monitoring)
- `rosa list` shows cluster without HCP flag

## Key Concepts
- **STS (Secure Token Service)**: short-lived credentials via IAM roles; no long-lived kubeconfig secrets
- **OCM**: OpenShift Cluster Manager — ROSA lifecycle API
- **Managed add-ons**: Red Hat or partner operators installed via OCM
- **AWS integration**: IRSA-style OIDC provider per cluster
- **CLI**: `oc` for cluster ops, `rosa` for cluster lifecycle, `aws` for IAM/VPC

## Commands and Patterns

```bash
# ROSA cluster list and describe
rosa list clusters
rosa describe cluster -c [cluster-name]

# Login
rosa login
oc login [api-url] --token=[token]

# STS and IAM
rosa describe cluster -c [cluster-name] -o json | jq '.aws.sts'
aws iam list-roles --query "Roles[?contains(RoleName,'OSD')]" 

# Add-on status
oc get addons -A 2>/dev/null || rosa list addons -c [cluster-name]
oc get csv -n openshift-operators | grep -v Succeeded

# Node and infra
oc get nodes -l node.openshift.io/os_id
oc get machines -n openshift-machine-api

# Upgrade
rosa describe upgrade policy -c [cluster-name]
oc get clusterversion
```

## Common Issues

**STS auth failure / token expired**
- Symptom: `Unauthorized` or `STS request failed`
- Re-authenticate: `rosa login` then `oc login`
- Verify OIDC provider: `aws iam list-open-id-connect-providers`
- See: runbook `platform-ops/runbooks/rosa/sts-auth-failure.md`

**Managed add-on Degraded**
- `oc get csv -A | grep -v Succeeded`
- Check OCM add-on state: `rosa list addons -c [cluster-name]`
- Reinstall via OCM console or `rosa install addon`
- See: runbook `platform-ops/runbooks/rosa/managed-addon-degraded.md`

**Insufficient node capacity**
- Check MachineSets: `oc get machinesets -n openshift-machine-api`
- AWS ASG events in console for the ROSA account
- Scale: `rosa edit machinepool` or OCM console

## References
- Runbooks: `platform-ops/runbooks/rosa/`
- Config base: `platform-config/base/rosa/`
- Cloud: `cloud/aws`
- HCP variant: `platform/rosa-hcp` (different architecture)
