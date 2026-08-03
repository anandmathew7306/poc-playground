---
name: platform/ocp
description: >
  Use when working on self-managed OpenShift Container Platform clusters.
  Covers cluster administration, Machine Config Operator, operators, and nodes.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: platform
refs:
  - core
---

# Platform/OCP

## When to Use
- Self-managed OCP clusters (on-prem or cloud-hosted)
- MCO upgrades, node scaling, operator troubleshooting
- ClusterVersion and Infrastructure resource changes
- Any task where `oc get infrastructure cluster` shows `Platform: None` or on-prem

## Key Concepts
- **ClusterVersion**: controls OCP version and upgrade channel
- **Machine Config Pool (MCP)**: groups nodes for config rollout (`worker`, `master`)
- **Cluster Operators**: platform components (`oc get co`)
- **OVN-Kubernetes**: default CNI; NetworkPolicy via `network-policy` CRs
- **CLI**: always `oc` (not `kubectl` alone) for OCP-specific resources

## Commands and Patterns

```bash
# Verify cluster and version
oc whoami
oc get clusterversion
oc get infrastructure cluster -o jsonpath='{.status.platform}{"\n"}'

# Node health
oc get nodes
oc get machineconfigpool
oc describe machineconfigpool worker

# Operator status
oc get co
oc get co | awk '$3!="True" && $4!="True" {print}'

# Upgrade status
oc adm upgrade
oc get clusterversion -o yaml | grep -A10 conditions

# Project and quota
oc get projects -l platform.io/client=[client]
oc describe quota -n [namespace]

# Debug pod on node
oc debug node/[node-name] -- chroot /host
```

## Common Issues

**Node NotReady after MCO rollout**
- Check MCP: `oc get mcp worker -o yaml | grep -A5 conditions`
- Paused pool: `oc patch mcp worker --type=merge -p '{"spec":{"paused":false}}'`
- See: `troubleshooting/ocp-nodes`, runbook `platform-ops/runbooks/ocp/node-notready.md`

**Operator Degraded**
- `oc get co [operator] -o yaml | grep -A5 "message"`
- Check operator pod logs in `openshift-[operator-name]` namespace
- See: `troubleshooting/ocp-operators`, runbook `platform-ops/runbooks/ocp/operator-degraded.md`

**MCO stuck / nodes not updating**
- `oc get mcp` — look for `UPDATING=True` stuck > 30 min
- Drain failures: check PDBs and pod disruption
- See: runbook `platform-ops/runbooks/ocp/mco-stuck.md`

**etcd unhealthy**
- `oc get etcd -o yaml` — check cluster health conditions
- Never force-delete etcd pods; escalate if quorum at risk
- See: runbook `platform-ops/runbooks/ocp/etcd-unhealthy.md`

## References
- Runbooks: `platform-ops/runbooks/ocp/`
- Config base: `platform-config/base/ocp/`
- Troubleshooting: `troubleshooting/ocp-nodes`, `troubleshooting/ocp-operators`
