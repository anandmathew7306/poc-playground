---
name: cloud/azure
description: >
  Use when working with Azure resources for platform clusters.
  Covers AKS, Azure AD, and Azure CLI patterns.
status: stub
reviewed_at: "2026-06-13"
version: 0.1.0
layer: cloud
refs:
  - core
---

# Cloud/Azure

> **Not yet active.** PlatRel does not operate Azure workloads today. This skill is a placeholder for future AKS onboarding. Do not use for production tasks — escalate to platform lead if a client requests Azure.

## When to Use
- **Future only**: when a client profile specifies `cloud: azure`
- Planning AKS cluster design or Entra ID integration
- Do **not** use for current incidents or changes

## Key Concepts (planned)
- **AKS**: Azure managed Kubernetes; `az aks` CLI
- **Entra ID**: workload identity and RBAC integration
- **Azure CNI**: overlay vs kubenet networking choices
- **Regions**: TBD based on client requirements

## Commands and Patterns (reference)

```bash
# Planned patterns — verify before use when skill goes active
az account show
az aks list --output table
az aks get-credentials --name [cluster] --resource-group [rg]
kubectl get nodes
```

## Common Issues
- N/A — skill not active. For Azure requests, open a platform roadmap ticket.

## References
- Platform matrix: `docs/platform-matrix.md` (Azure: stub)
- When activated: will compose with `platform/eks` patterns adapted for AKS
