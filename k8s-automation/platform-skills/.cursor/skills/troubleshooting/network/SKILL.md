---
name: troubleshooting/network
description: >
  Use when diagnosing pod networking, DNS, egress, and NetworkPolicy issues.
  Covers OVN-Kubernetes, CoreDNS, and egress IP on OCP/ROSA.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: troubleshooting
refs:
  - core
  - platform/ocp
---

# Troubleshooting/Network

## When to Use
- Pod-to-pod connectivity failures
- DNS resolution errors (`nslookup`, `dig` failing in pods)
- Egress IP not working for outbound allowlisting
- NetworkPolicy blocking legitimate traffic

## Key Concepts
- **OVN-Kubernetes**: default CNI on OCP 4.12+; handles NetworkPolicy via ACLs
- **CoreDNS**: cluster DNS in `openshift-dns` (OCP) or `kube-system` (EKS)
- **EgressIP**: OCP feature for stable outbound IPs per namespace
- **NetworkPolicy**: default-deny per `core` runtime contract — explicit allows required
- **EKS**: VPC CNI, security groups, and `kubectl` NetworkPolicy

## Commands and Patterns

```bash
# DNS (OCP/ROSA)
oc get pods -n openshift-dns
oc run dns-test --image=registry.redhat.io/ubi9/ubi-minimal --rm -it --restart=Never -- nslookup kubernetes.default

# OVN (OCP)
oc get pods -n openshift-ovn-kubernetes
oc logs -n openshift-ovn-kubernetes -l app=ovnkube-node --tail=30 -c ovnkube-node

# NetworkPolicy
oc get networkpolicy -n [namespace]
oc describe networkpolicy [name] -n [namespace]

# EgressIP
oc get egressip
oc get egressip -o yaml | grep -A10 "status"

# Pod connectivity test
oc run nettest --image=registry.redhat.io/ubi9/ubi-minimal --rm -it --restart=Never -n [ns] -- curl -sS --max-time 5 http://[svc].[ns].svc:8080/healthz

# EKS DNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=aws-node --tail=30
```

## Common Issues

**DNS resolution failure**
- CoreDNS pods not running or overloaded
- OVN DNS service misconfigured after upgrade
- See: runbook `platform-ops/runbooks/network/dns-resolution-failure.md`

**Pod connectivity — NetworkPolicy**
- Default-deny in namespace blocks traffic
- `oc describe networkpolicy` — check ingress/egress rules
- Temporarily label pod for debugging in nonprod only

**Egress IP not working**
- EgressIP not assigned to correct nodes
- Namespace missing `platform.io/egress=enabled` label (client-specific)
- See: runbook `platform-ops/runbooks/network/egress-ip-not-working.md`

**OVN pod connectivity**
- ovnkube-node pod unhealthy on specific node
- See: runbook `platform-ops/runbooks/network/ovn-pod-connectivity.md`

## References
- Runbooks: `platform-ops/runbooks/network/`
- Runtime contract: `core` (NetworkPolicy default deny)
- EKS networking: `platform/eks`, `cloud/aws`
