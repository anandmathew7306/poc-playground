---
title: "DNS Resolution Failure"
platform: "all"
severity: "P1"
last_updated: "2026-06-13"
last_tested: ""
author: "platrel"
---

# DNS Resolution Failure

## Symptom
Alert `CoreDNSDown`, `DNSLatencyHigh`, or application errors show `Name or service not known`, `NXDOMAIN`, or `connection timed out` on DNS lookups. `oc exec` or `kubectl exec` `nslookup kubernetes.default` fails from application pods. External DNS resolution may also fail.

## Impact
Service discovery breaks — pods cannot resolve ClusterIP service names or external endpoints. Application startup fails, inter-service calls return errors, and ingress routing may degrade. All workloads depending on DNS are affected.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check DNS operator and CoreDNS pods (OCP)
oc get clusteroperator dns
oc get pods -n openshift-dns -o wide

# For EKS:
kubectl get pods -n kube-system -l k8s-app=kube-dns

# 2. Test DNS resolution from a test pod
oc run dnstest --image=registry.redhat.io/rhel9/rhel --rm -it --restart=Never -n <namespace> -- \
  nslookup kubernetes.default.svc.cluster.local

# 3. Check DNS operator logs and NodeResolver config
oc logs -n openshift-dns-operator deployment/dns-operator --tail=50
oc get dns.config/cluster -o yaml
```

## Common Causes

### Cause 1: CoreDNS Pods Not Running or Overloaded
**Symptoms:** CoreDNS pods in `CrashLoopBackOff` or CPU throttled; DNS queries time out under load; `oc logs` shows `plugin/forward: no such host` or OOMKilled; only intermittent failures at high QPS
**Fix:**
```bash
# Check CoreDNS pod status and resource usage
oc get pods -n openshift-dns -o wide
oc top pods -n openshift-dns

# Review CoreDNS logs
oc logs -n openshift-dns deployment/dns-default --tail=100

# Scale CoreDNS if under-resourced (OCP manages via DNS operator)
oc patch dns.config/cluster --type=merge -p '{"spec":{"upstreamResolvers":{"policy":"Sequential"}}}'

# Restart CoreDNS pods
oc rollout restart deployment/dns-default -n openshift-dns
oc get pods -n openshift-dns -w

# Verify resolution
oc run dnstest --image=registry.redhat.io/rhel9/rhel --rm -it --restart=Never -- \
  nslookup <service>.<namespace>.svc.cluster.local
```

### Cause 2: Upstream DNS or NetworkPolicy Misconfiguration
**Symptoms:** Internal cluster DNS works but external resolution fails; `nslookup google.com` fails from pods; EgressFirewall or NetworkPolicy blocks UDP/TCP port 53; upstream resolver IP changed
**Fix:**
```bash
# Check upstream resolver configuration
oc get dns.config/cluster -o yaml

# Test upstream DNS from a node
oc debug node/<node-name> -- chroot /host nslookup google.com <upstream-dns-ip>

# Check for policies blocking DNS egress
oc get networkpolicy -n <namespace>
oc get egressfirewall -n <namespace>

# Update upstream resolvers if changed (requires change ticket)
oc patch dns.config/cluster --type=merge -p \
  '{"spec":{"upstreamResolvers":{"upstreamServers":[{"address":"<correct-dns-ip>"}]}}}'

# Verify external resolution from pod
oc exec -n <namespace> <pod-name> -- nslookup <external-hostname>
```

## Escalation Criteria
Escalate to next level if:
- [ ] DNS failure is cluster-wide and CoreDNS restart does not help
- [ ] Upstream DNS provider outage suspected
- [ ] Issue blocks production deployments for more than 20 minutes
- [ ] More than 30 minutes elapsed without progress

## Related
- Skill: troubleshooting/network
- Skill: platform/ocp
- Skill: platform/eks
- Runbook: runbooks/network/ovn-pod-connectivity.md
- Runbook: runbooks/ocp/operator-degraded.md
- Dashboard: Grafana → Networking / DNS

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Filled operational troubleshooting content |
