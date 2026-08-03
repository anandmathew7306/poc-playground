---
name: observability/logging
description: >
  Use when working with cluster logging and log aggregation.
  Covers Loki, Fluentd, and log forwarding on platform clusters.
status: stub
reviewed_at: "2026-06-13"
version: 0.1.0
layer: observability
refs:
  - core
---

# Observability/Logging

> **Not yet active.** PlatRel uses platform-default logging (Cluster Logging Operator on OCP/ROSA, CloudWatch on EKS) but has not standardized a team-wide logging skill. Use runbooks and platform-specific docs for log access until this skill is activated.

## When to Use
- **Future**: Loki/Grafana stack deployment and query patterns
- **Future**: Log-based alert rules and retention policies
- **Now**: basic log access via `oc logs` / `kubectl logs` and cloud console

## Key Concepts (planned)
- **Cluster Logging Operator**: Fluentd/Vector forwarding on OCP/ROSA
- **Loki**: label-based log aggregation paired with Grafana
- **Retention**: client compliance drives retention (see profile `audit_logging`)
- **No PII**: confidential clients (e.g. Acme) — no client data in logs

## Commands and Patterns (current baseline)

```bash
# Pod logs (all platforms)
oc logs [pod] -n [namespace] --tail=100
oc logs [pod] -n [namespace] -c [container] --previous   # crashed pod

# OCP/ROSA cluster logging
oc get clusterlogforwarder -n openshift-logging
oc get pods -n openshift-logging

# EKS — CloudWatch
aws logs describe-log-groups --log-group-name-prefix /aws/eks/[cluster]
```

## Common Issues
- For log access issues, use platform skill and cloud console
- Audit logging requirements: check client `profile.yaml` compliance section

## References
- Compliance: client `profile.yaml` → `audit_logging`
- When activated: will compose with `observability/prometheus` for correlated alerts
