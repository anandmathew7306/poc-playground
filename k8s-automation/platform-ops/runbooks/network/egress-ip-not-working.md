---
title: "Egress IP Not Working"
platform: "ocp"
severity: "P2"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# Egress IP Not Working

## Symptom
Alert `EgressIPAssignmentFailed` fires or applications report outbound connections using unexpected source IPs. Partner allowlists reject traffic because the cluster no longer egresses from the assigned IP. `oc get egressip` shows `EgressIPAssigned=False` or wrong node assignment.

## Impact
Outbound traffic from affected namespaces uses node IPs instead of the designated egress IP. External services with IP allowlists block the traffic — API integrations, payment gateways, and SaaS webhooks fail. Compliance requirements for fixed egress IPs may be violated.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check EgressIP resource status
oc get egressip -A
oc describe egressip <egressip-name>

# 2. Verify EgressIP assigned to correct nodes
oc get egressip <egressip-name> -o jsonpath='{.status.items}'
oc get nodes -l k8s.ovn.org/egress-assignable=

# 3. Check OVN-Kubernetes and egress IP controller logs
oc logs -n openshift-ovn-kubernetes -l app=ovnkube-control-plane --tail=50
oc get events -A --field-selector reason=EgressIP --sort-by='.lastTimestamp'
```

## Common Causes

### Cause 1: No Node Labeled as Egress-Assignable
**Symptoms:** EgressIP status shows `NoMatchingNodeFound`; no nodes carry `k8s.ovn.org/egress-assignable` label; recently scaled down node pool removed the labeled node
**Fix:**
```bash
# Check for egress-assignable nodes
oc get nodes -l k8s.ovn.org/egress-assignable

# Label appropriate nodes (typically infra nodes)
oc label node <infra-node-name> k8s.ovn.org/egress-assignable=

# Verify EgressIP reassigns
oc get egressip <egressip-name> -w

# Test outbound IP from a pod in the target namespace
oc exec -n <namespace> <pod-name> -- curl -s https://ifconfig.me
```

### Cause 2: Cloud Provider Routing or IP Not Associated
**Symptoms:** EgressIP shows assigned to a node but outbound traffic uses a different IP; AWS/Azure route table missing host route for the egress IP; `oc describe egressip` shows `CloudPrivateIPNotAllocated`
**Fix:**
```bash
# Check EgressIP assignment details
oc get egressip <egressip-name> -o yaml

# On AWS: verify secondary IP on ENI
aws ec2 describe-network-interfaces --filters "Name=addresses.private-ip-address,Values=<egress-ip>"

# Check route table has host route for egress IP on the assigned node
# (OCP cloud controller should manage this — check cloud-controller-manager logs)
oc logs -n openshift-cloud-controller-manager -l app=cloud-controller-manager --tail=50

# Delete and recreate EgressIP to force re-provisioning (maintenance window)
oc delete egressip <egressip-name>
# Reapply from platform-config GitOps source
oc get egressip <egressip-name> -w
```

## Escalation Criteria
Escalate to next level if:
- [ ] Production partner integrations blocked for more than 30 minutes
- [ ] Cloud route table changes required (network team / cloud admin)
- [ ] EgressIP reassignment fails on all candidate nodes
- [ ] More than 60 minutes elapsed without progress

## Related
- Skill: troubleshooting/network
- Skill: platform/ocp
- Skill: cloud/aws
- Runbook: runbooks/network/ovn-pod-connectivity.md
- Runbook: runbooks/ocp/node-notready.md
- Dashboard: Grafana → Networking / Egress IP

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
