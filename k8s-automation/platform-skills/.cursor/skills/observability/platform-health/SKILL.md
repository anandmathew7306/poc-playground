---
name: observability/platform-health
description: >
  Use when assessing overall cluster and platform component health.
  Covers operator status, node readiness, monitoring stack, and ACM compliance.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: observability
refs:
  - core
  - observability/prometheus
---

# Observability/Platform Health

## When to Use
- Routine health checks (daily or pre-change)
- `tasks/platform-health-check` skill composition
- Post-incident verification that platform is stable
- Onboarding validation (Week 2 bootcamp)

## Key Concepts
- **Health dimensions**: nodes, operators, monitoring, ACM compliance, workloads
- **Red / Yellow / Green**: classify each dimension for reporting
- **Platform-specific**: use correct skill (`platform/ocp`, `platform/rosa-hcp`, etc.)
- **Output**: structured summary for client ticket or Confluence

## Commands and Patterns

```bash
# === Nodes ===
oc get nodes
oc get nodes | grep -v Ready && echo "FAIL: nodes not ready" || echo "OK: all nodes ready"

# === Cluster operators (OCP/ROSA) ===
oc get co
oc get co -o json | jq -r '.items[] | select(.status.conditions[]? | select(.type=="Available" and .status!="True")) | .metadata.name'

# === Monitoring stack ===
oc get prometheus,alertmanager -n openshift-monitoring
oc get prometheusrule -n openshift-monitoring --no-headers | wc -l

# === ACM compliance (hub) ===
oc get policies -n open-cluster-management -o custom-columns=NAME:.metadata.name,COMPLIANT:.status.compliant | grep NonCompliant

# === Workloads (client namespaces) ===
oc get pods -n [client-ns] --field-selector=status.phase!=Running,status.phase!=Succeeded

# === API health ===
oc get --raw /healthz
oc get --raw /readyz

# === EKS variant ===
kubectl get nodes
kubectl get pods -n kube-system
kubectl get pods -A --field-selector=status.phase!=Running | head -20
```

## Health Report Template

```
Platform Health Check — [client] — [date]
Cluster: [name] | Platform: [platform] | Region: [region]

| Dimension        | Status | Notes |
|------------------|--------|-------|
| Nodes            | G/Y/R  |       |
| Operators        | G/Y/R  |       |
| Monitoring       | G/Y/R  |       |
| ACM compliance   | G/Y/R  |       |
| Client workloads | G/Y/R  |       |
```

## Common Issues

**Yellow: single operator degraded**
- Non-critical operator (e.g. console) — schedule fix in business hours
- Reference `troubleshooting/ocp-operators`

**Red: multiple operators or API unhealthy**
- P2 incident — load `tasks/incident-response`
- Check etcd, API server pods if OCP

**NonCompliant ACM policies**
- Load `troubleshooting/acm-policies`
- Distinguish audit vs enforce violations

## References
- Task workflow: `tasks/platform-health-check`
- Prometheus detail: `observability/prometheus`
- Runbooks: `platform-ops/runbooks/`
