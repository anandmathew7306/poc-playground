---
title: "etcd Unhealthy"
platform: "ocp"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# etcd Unhealthy

## Symptom
Alert `etcdMembersDown`, `etcdHighNumberOfFailedGRPCRequests`, or `etcdDatabaseHighFragmentation` fires. `oc get etcd` shows members not `HEALTHY` or ClusterOperator `etcd` is `DEGRADED=True`. API server latency spikes; `oc` commands time out intermittently.

## Impact
etcd is the cluster's source of truth. Degradation causes API instability, failed deployments, operator reconciliation loops, and risk of split-brain or data loss if not addressed promptly. This is a P1 control-plane incident.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check etcd ClusterOperator and member health
oc get clusteroperator etcd
oc get etcd -o yaml

# 2. Check etcd pod status on control plane nodes
oc get pods -n openshift-etcd -o wide
oc get pods -n openshift-etcd -l app=etcd

# 3. Review etcd operator and member logs
oc logs -n openshift-etcd-operator deployment/etcd-operator --tail=50
oc logs -n openshift-etcd etcd-<member-name> --tail=50
```

## Common Causes

### Cause 1: etcd Member Pod Not Running or Disk Full
**Symptoms:** One etcd pod in `CrashLoopBackOff` or `Pending`; logs show `no space left on device` or `wal sync duration`; member count below quorum threshold
**Fix:**
```bash
# Check etcd pod status and node disk
oc get pods -n openshift-etcd -o wide
oc describe pod -n openshift-etcd etcd-<member-name>

# Check disk on control plane node (via debug)
oc debug node/<control-plane-node> -- chroot /host df -h /var/lib/etcd

# If disk full, compact and defrag (etcdctl via debug pod — maintenance window required)
oc debug -n openshift-etcd etcd-<member-name> -- \
  etcdctl endpoint status --cluster -w table

# Restart failed etcd static pod after resolving disk issue
oc debug node/<control-plane-node> -- chroot /host systemctl restart etcd-member
```

### Cause 2: Leader Election Failure or Network Latency
**Symptoms:** etcd logs show `rafthttp: failed to dial`; high `etcd_disk_wal_fsync_duration_seconds`; multiple members report `unhealthy`; inter-control-plane network issues
**Fix:**
```bash
# Check etcd member list and leader
oc exec -n openshift-etcd etcd-<member-name> -- \
  etcdctl member list -w table

# Verify network between control plane nodes
oc debug node/<cp-node-1> -- chroot /host ping -c 3 <cp-node-2-ip>

# Check for MTU or firewall changes in recent change window
oc get events -n openshift-etcd --sort-by='.lastTimestamp' | tail -20

# If single member is isolated, cordon workloads and involve platform lead
# Do NOT remove etcd members without runbook approval and backup
```

## Escalation Criteria
Escalate to next level if:
- [ ] Quorum is at risk (fewer than majority of members healthy)
- [ ] API server unavailable or severely degraded
- [ ] Disk compaction/defrag does not resolve within 15 minutes
- [ ] More than 20 minutes elapsed without progress — page platform lead immediately

## Related
- Skill: platform/ocp
- Skill: troubleshooting/ocp-operators
- Runbook: runbooks/ocp/operator-degraded.md
- Runbook: runbooks/network/ovn-pod-connectivity.md
- Dashboard: Grafana → Platform / etcd

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
