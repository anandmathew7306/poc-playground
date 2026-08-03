---
title: "Node NotReady"
platform: "ocp"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Node NotReady

## Symptom
Alert `KubeNodeNotReady` or `NodeConditionUnknown` fires. `oc get nodes` shows one or more nodes with `STATUS=NotReady` or `STATUS=Unknown`. Pods on affected nodes enter `Terminating` or remain `Pending` with events like `0/X nodes are available: node(s) had untolerated taint`.

## Impact
Workloads scheduled on the affected node lose capacity. Stateful workloads may experience disruption if PDBs are violated. Cluster autoscaling may not replace nodes fast enough, causing cascading scheduling failures and SLO breaches.

## Quick Checks
Run these first — in this order:

```bash
# 1. Identify NotReady nodes and conditions
oc get nodes -o wide
oc get nodes -o json | jq -r '.items[] | select(.status.conditions[] | select(.type=="Ready" and .status!="True")) | .metadata.name'

# 2. Inspect node conditions and events
oc describe node <node-name>

# 3. Check kubelet and node logs on the affected node (via debug pod or SSH if permitted)
oc adm node-logs <node-name> --bootkube kubelet --tail=50
oc adm node-logs <node-name> --bootkube crio --tail=50
```

## Common Causes

### Cause 1: Kubelet or CRI-O Failure
**Symptoms:** Node `Ready=False` with reason `KubeletNotReady` or `ContainerRuntimeNotReady`; kubelet logs show `failed to start container` or `PLEG is not healthy`
**Fix:**
```bash
# Drain the node to evacuate workloads
oc adm drain <node-name> --ignore-daemonsets --delete-emptydir-data --force

# Restart kubelet via Machine Config (preferred on OCP)
oc debug node/<node-name> -- chroot /host systemctl restart kubelet

# If CRI-O is hung, restart it
oc debug node/<node-name> -- chroot /host systemctl restart crio

# Uncordon once Ready
oc get node <node-name>
oc adm uncordon <node-name>
```

### Cause 2: Disk Pressure or Network Partition
**Symptoms:** Node shows `DiskPressure=True` or `NetworkUnavailable=True`; describe output shows `EvictionThresholdMet` or `NoRouteToHost` in events
**Fix:**
```bash
# Check disk usage on the node
oc debug node/<node-name> -- chroot /host df -h /var/lib/containers /var/lib/kubelet

# Prune unused images if disk pressure
oc debug node/<node-name> -- chroot /host crictl rmi --prune

# Verify network connectivity to API server
oc debug node/<node-name> -- chroot /host curl -k https://api-int.<cluster>:6443/healthz

# If network partition persists, cordon and replace via MachineSet
oc adm cordon <node-name>
oc scale machineset <machineset-name> -n openshift-machine-api --replicas=<current+1>
```

## Escalation Criteria
Escalate to next level if:
- [ ] More than one node is NotReady simultaneously
- [ ] Node does not return to Ready within 20 minutes after remediation
- [ ] Root cause indicates hardware failure or storage backend outage
- [ ] More than 30 minutes elapsed without progress

## Related
- Skill: troubleshooting/ocp-nodes
- Skill: platform/ocp
- Runbook: runbooks/ocp/mco-stuck.md
- Runbook: runbooks/ocp/operator-degraded.md
- Dashboard: Grafana → Platform / Node Health

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
