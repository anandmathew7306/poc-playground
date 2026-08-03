---
title: "Node NotReady"
platform: "eks"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Node NotReady

## Symptom
Alert `KubeNodeNotReady` fires on an EKS cluster. `kubectl get nodes` shows `NotReady` or `Unknown` status. AWS Console shows the underlying EC2 instance as `running` but the node is not registering with the API server, or the instance is `stopped`/`terminated`.

## Impact
Pod scheduling capacity is reduced. Workloads on the affected node may be evicted or stuck terminating. Cluster Autoscaler may not provision replacements if the node group is at max size or misconfigured.

## Quick Checks
Run these first — in this order:

```bash
# 1. Identify NotReady nodes
kubectl get nodes -o wide
kubectl describe node <node-name>

# 2. Map node to EC2 instance and check instance state
kubectl get node <node-name> -o jsonpath='{.spec.providerID}'
aws ec2 describe-instances --instance-ids <instance-id> --query 'Reservations[0].Instances[0].State'

# 3. Check node group and ASG health
aws eks describe-nodegroup --cluster-name <cluster> --nodegroup-name <nodegroup>
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names <asg-name>
```

## Common Causes

### Cause 1: Kubelet Not Running or Bootstrap Failure
**Symptoms:** EC2 instance is `running` but node stays `NotReady`; node conditions show `KubeletNotReady`; SSM or serial console shows kubelet service failed; `/etc/eks/bootstrap.sh` errors in cloud-init logs
**Fix:**
```bash
# Check node conditions and kubelet logs via SSM (if enabled)
aws ssm start-session --target <instance-id>
# On the node:
sudo systemctl status kubelet
sudo journalctl -u kubelet --no-pager -n 50

# Restart kubelet
sudo systemctl restart kubelet

# If bootstrap failed, cordon and terminate to let ASG replace
kubectl cordon <node-name>
aws autoscaling terminate-instance-in-auto-scaling-group \
  --instance-id <instance-id> --no-should-decrement-desired-capacity
```

### Cause 2: Node Group or ASG at Capacity / Instance Unhealthy
**Symptoms:** ASG shows instances in `Unhealthy` state; Cluster Autoscaler logs show `max node group size reached`; new instances launch but fail health checks; subnet IP exhaustion
**Fix:**
```bash
# Check ASG activities for launch failures
aws autoscaling describe-scaling-activities --auto-scaling-group-name <asg-name> --max-items 5

# Verify node group scaling config
aws eks describe-nodegroup --cluster-name <cluster> --nodegroup-name <nodegroup> \
  --query 'nodegroup.scalingConfig'

# Scale up node group if at minimum and workloads pending
aws eks update-nodegroup-config --cluster-name <cluster> --nodegroup-name <nodegroup> \
  --scaling-config minSize=2,maxSize=10,desiredSize=4

# Check subnet IP availability
aws ec2 describe-subnets --subnet-ids <subnet-id> --query 'Subnets[0].AvailableIpAddressCount'
```

## Escalation Criteria
Escalate to next level if:
- [ ] More than 25% of nodes are NotReady
- [ ] Node group scaling does not replace failed nodes within 20 minutes
- [ ] Underlying EC2 instances are being terminated unexpectedly (spot interruption storm)
- [ ] More than 30 minutes elapsed without progress

## Related
- Skill: platform/eks
- Skill: cloud/aws
- Runbook: runbooks/eks/addon-degraded.md
- Runbook: runbooks/network/dns-resolution-failure.md
- Dashboard: Grafana → EKS / Node Health

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
