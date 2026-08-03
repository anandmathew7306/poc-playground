---
title: "OVN Pod Connectivity Failure"
platform: "ocp"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# OVN Pod Connectivity Failure

## Symptom
Alert `OVNKubernetesControllerDisconnected` or application alerts show pod-to-pod connectivity failures. `oc exec` ping/curl between pods in the same namespace fails. OVN-Kubernetes controller logs show reconciliation errors. NetworkPolicy tests fail unexpectedly.

## Impact
Microservice communication breaks — APIs return 503, databases become unreachable from application pods, and service mesh routes fail. East-west traffic within the cluster is impaired, directly affecting application availability SLOs.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check OVN-Kubernetes and network operator status
oc get clusteroperator network
oc get pods -n openshift-ovn-kubernetes -o wide

# 2. Verify OVN databases and controller health
oc get pods -n openshift-ovn-kubernetes -l app=ovnkube-control-plane
oc logs -n openshift-ovn-kubernetes -l app=ovnkube-node --tail=30 -c ovnkube-node

# 3. Test pod-to-pod connectivity in affected namespace
oc run nettest-src --image=registry.redhat.io/rhel9/rhel --rm -it --restart=Never -n <namespace> -- \
  ping -c 3 <target-pod-ip>
```

## Common Causes

### Cause 1: OVN-Kubernetes Node Agent Not Running
**Symptoms:** `ovnkube-node` pod on specific node in `CrashLoopBackOff`; only pods on that node cannot reach others; node logs show `failed to configure OVS bridge` or `geneve port error`
**Fix:**
```bash
# Identify nodes with unhealthy ovnkube-node pods
oc get pods -n openshift-ovn-kubernetes -o wide | grep -v Running

# Check logs on the failing node agent
oc logs -n openshift-ovn-kubernetes -l app=ovnkube-node --field-selector spec.nodeName=<node-name> -c ovnkube-node --tail=100

# Restart ovnkube-node on the affected node
oc delete pod -n openshift-ovn-kubernetes -l app=ovnkube-node --field-selector spec.nodeName=<node-name>

# If persistent, drain and reboot the node
oc adm drain <node-name> --ignore-daemonsets --delete-emptydir-data
oc debug node/<node-name> -- chroot /host systemctl reboot
oc adm uncordon <node-name>
```

### Cause 2: NetworkPolicy or EgressFirewall Blocking Traffic
**Symptoms:** Connectivity fails only between specific namespaces; `oc describe networkpolicy` shows deny rules matching the traffic; EgressFirewall in `openshift-network-node-identity` or project blocks CIDR; works after policy removal
**Fix:**
```bash
# List policies in source and destination namespaces
oc get networkpolicy -n <source-namespace>
oc get networkpolicy -n <dest-namespace>
oc get egressfirewall -n <namespace>

# Describe matching policies
oc describe networkpolicy <policy-name> -n <namespace>

# Test without policies (temporary — maintenance window only)
oc label namespace <namespace> network-policy-test=true
# Adjust policy to allow required traffic (preferred fix)
oc edit networkpolicy <policy-name> -n <namespace>

# Verify connectivity restored
oc exec -n <source-namespace> <pod-name> -- curl -s --max-time 5 http://<dest-service>:8080/healthz
```

## Escalation Criteria
Escalate to next level if:
- [ ] Cluster-wide connectivity failure (all namespaces affected)
- [ ] OVN control plane pods unhealthy on multiple nodes
- [ ] Issue persists after node agent restart and policy review
- [ ] More than 30 minutes elapsed without progress

## Related
- Skill: troubleshooting/network
- Skill: platform/ocp
- Runbook: runbooks/network/dns-resolution-failure.md
- Runbook: runbooks/network/egress-ip-not-working.md
- Runbook: runbooks/ocp/node-notready.md
- Dashboard: Grafana → Networking / OVN

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
