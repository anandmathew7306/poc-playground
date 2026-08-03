---
name: platform/rosa-hcp
description: >
  Use when working on ROSA with Hosted Control Planes (Hypershift).
  Covers HostedCluster, NodePool, management cluster, and worker provisioning.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: platform
refs:
  - core
  - cloud/aws
---

# Platform/ROSA HCP

## When to Use
- ROSA Hypershift / Hosted Control Plane clusters
- HostedCluster or NodePool degraded alerts
- Management cluster operations (hypershift operator namespace)
- Client profile specifies `platform: rosa-hcp` (e.g. Acme)

## Key Concepts
- **Management cluster**: hosts Hypershift operator; runs `oc` against HostedCluster CRs
- **HostedCluster**: control plane runs as pods on management cluster; workers on AWS
- **NodePool**: worker node scaling; maps to AWS Auto Scaling Groups
- **HostedCluster namespace**: typically `clusters-[cluster-name]`
- **Kubeconfig**: separate API endpoint per hosted cluster via `oc get hc -o yaml`

## Commands and Patterns

```bash
# Management cluster — list hosted clusters
oc get hostedcluster -A
oc get hostedcluster [name] -n clusters-[name]

# HostedCluster conditions
oc describe hostedcluster [name] -n clusters-[name]
oc get hostedcluster [name] -n clusters-[name] -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.message}{"\n"}{end}'

# NodePool
oc get nodepool -n clusters-[name]
oc describe nodepool [pool-name] -n clusters-[name]

# Scale workers
oc patch nodepool [pool-name] -n clusters-[name] \
  --type=merge -p '{"spec":{"replicas":3}}'

# Access hosted cluster API (get kubeconfig secret)
oc get secret -n clusters-[name] | grep kubeconfig
oc extract secret/[cluster]-admin-kubeconfig -n clusters-[name] --to=- > /tmp/kc.yaml
export KUBECONFIG=/tmp/kc.yaml
oc get nodes

# Hypershift operator health (management cluster)
oc get deployment -n hypershift
oc logs -n hypershift deployment/operator --tail=50
```

## Common Issues

**HostedCluster Degraded**
- Check NodePool first — most common root cause
- AWS quota: `InsufficientInstanceCapacity`, `VcpuLimitExceeded`
- See: runbook `platform-ops/runbooks/rosa-hcp/hostedcluster-degraded.md`

**NodePool unavailable / nodes not joining**
- `oc describe nodepool` for launch failures
- Verify subnet, security groups, IAM instance profile in AWS console
- See: runbook `platform-ops/runbooks/rosa-hcp/nodepool-unavailable.md`

**API unreachable on hosted cluster**
- Control plane pods on management cluster: `oc get pods -n clusters-[name]`
- Check Route53/private DNS for API endpoint
- Escalate to Red Hat if control plane pods crash-looping > 15 min

## References
- Runbooks: `platform-ops/runbooks/rosa-hcp/`
- Config base: `platform-config/base/rosa/`
- Cloud: `cloud/aws`
- Example client: `clients/acme/SKILL.md`
