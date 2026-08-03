---
title: "Machine Config Operator Stuck"
platform: "ocp"
severity: "P2"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Machine Config Operator Stuck

## Symptom
Alert `MachineConfigPoolDegraded` or `MachineConfigPoolUpdating` fires and persists. `oc get mcp` shows a pool stuck in `UPDATING=True` or `DEGRADED=True` for more than 30 minutes. Nodes may show `config-version` mismatch or `required-signature` annotation conflicts.

## Impact
Node configuration changes (kubelet, kernel, CRI-O) cannot roll out. Cluster upgrades and security patches stall. Nodes may run inconsistent configurations, causing unpredictable workload behaviour.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check MachineConfigPool status
oc get machineconfigpool
oc describe machineconfigpool worker

# 2. Compare node config versions against pool target
oc get nodes -o json | jq -r '.items[] | "\(.metadata.name) \(.metadata.annotations["machineconfiguration.openshift.io/currentConfig"])"'

# 3. Check MCO pods and machine-config-daemon logs
oc get pods -n openshift-machine-config-operator
oc logs -n openshift-machine-config-operator daemonset/machine-config-daemon --tail=50 -l machineconfiguration.openshift.io/role=worker
```

## Common Causes

### Cause 1: Node Stuck During Drain or Reboot
**Symptoms:** One node shows `UPDATED=False` while others are `True`; MCD logs show `drain failed` or node has `reboot-needed` annotation but has not rebooted
**Fix:**
```bash
# Identify the stuck node
oc get machineconfigpool worker -o yaml | grep -A20 machineCount

# Check MCD logs on the stuck node
oc logs -n openshift-machine-config-operator -l machineconfiguration.openshift.io/role=worker --field-selector spec.nodeName=<node-name> --tail=100

# Manually drain and reboot if safe (during maintenance window)
oc adm drain <node-name> --ignore-daemonsets --delete-emptydir-data --force
oc debug node/<node-name> -- chroot /host systemctl reboot

# After reboot, verify node rejoins pool
oc get machineconfigpool worker -w
```

### Cause 2: Custom MachineConfig Conflict or Invalid Render
**Symptoms:** Pool `DEGRADED=True` with message about render failure; `oc get machineconfig` shows conflicting or duplicate entries; MCO controller logs show `error rendering`
**Fix:**
```bash
# List custom machine configs
oc get machineconfig | grep -v rendered

# Check MCO controller logs for render errors
oc logs -n openshift-machine-config-operator deployment/machine-config-controller --tail=100

# Remove or fix conflicting custom MachineConfig (requires change ticket)
oc get machineconfig <custom-mc-name> -o yaml
# After fix, delete stuck rendered config to force re-render
oc delete machineconfig rendered-worker-<hash>  # only the stuck rendered config

# Verify pool recovers
oc get machineconfigpool worker
```

## Escalation Criteria
Escalate to next level if:
- [ ] MCP remains UPDATING for more than 60 minutes
- [ ] Multiple nodes stuck simultaneously
- [ ] Issue blocks an in-progress cluster upgrade
- [ ] Custom MachineConfig rollback does not resolve degradation

## Related
- Skill: troubleshooting/ocp-operators
- Skill: platform/ocp
- Runbook: runbooks/ocp/node-notready.md
- Runbook: runbooks/ocp/operator-degraded.md
- Dashboard: Grafana → Platform / Machine Config

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
