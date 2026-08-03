---
name: troubleshooting/ocp-nodes
description: >
  Use when diagnosing OpenShift node NotReady, scheduling, or capacity issues.
  Covers Machine Config Pool, drains, and node conditions.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: troubleshooting
refs:
  - core
  - platform/ocp
---

# Troubleshooting/OCP Nodes

## When to Use
- Node `NotReady` or `SchedulingDisabled`
- Pods stuck Pending due to node capacity or taints
- MCO rollout affecting node health
- Alerts: `KubeNodeNotReady`, `NodeFilesystemSpaceFillingUp`

## Key Concepts
- **Node conditions**: `Ready`, `DiskPressure`, `MemoryPressure`, `PIDPressure`
- **MCP**: Machine Config Pool rolls config to nodes; stalled rollouts block readiness
- **Taints**: `node.kubernetes.io/unschedulable` during drain/upgrade
- **Debug**: `oc debug node/[name]` for on-node inspection (OCP)

## Commands and Patterns

```bash
# Node status
oc get nodes -o wide
oc describe node [node-name]

# Conditions and events
oc get node [node-name] -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}{"\n"}{end}'

# Machine Config Pool
oc get mcp
oc describe mcp worker

# Pods on node
oc get pods -A --field-selector spec.nodeName=[node-name] | grep -v Running

# Drain simulation (do not run in prod without ticket)
oc adm drain [node-name] --dry-run=server --ignore-daemonsets

# On-node debug
oc debug node/[node-name] -- chroot /host journalctl -u kubelet --no-pager -n 50
```

## Common Issues

**NotReady — kubelet not responding**
- `oc describe node` → `KubeletNotReady` message
- Debug node: check kubelet, CRI-O/containerd status
- If hardware: escalate to infra; if software: restart kubelet via MCO or `systemctl`

**NotReady — DiskPressure**
- Clean unused images: debug node → `crictl rmi --prune`
- Expand disk or add storage class capacity

**SchedulingDisabled during upgrade**
- Expected during cluster upgrade; verify `oc get clusterversion`
- If stuck > 60 min: check MCP and `oc adm upgrade`

**Insufficient capacity — pods Pending**
- `oc describe pod [pod]` → `FailedScheduling` events
- Scale MachineSet or add nodes: `oc scale machineset [name] -n openshift-machine-api --replicas=N`

## References
- Platform: `platform/ocp`
- Runbook: `platform-ops/runbooks/ocp/node-notready.md`
- MCO issues: `platform-ops/runbooks/ocp/mco-stuck.md`
