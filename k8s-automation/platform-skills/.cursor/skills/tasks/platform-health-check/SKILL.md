---
name: tasks/platform-health-check
description: >
  Use when running a structured platform health assessment for a client cluster.
  Covers nodes, operators, monitoring, ACM, and workloads.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: tasks
refs:
  - core
  - observability/platform-health
  - observability/prometheus
---

# Tasks/Platform Health Check

## When to Use
- Daily or weekly health checks
- Pre/post change validation
- Client onboarding Step 5
- Prompt: `client: [name] | task: platform-health-check`

## How This Skill Composes
Load `profile.yaml` → resolve `platform_skill` and `observability_skill`.
Execute checks via `observability/platform-health` — this task skill adds client-specific steps and reporting.

## Step 1 — Load client context
```bash
# From profile.yaml:
#   platform_skill, cluster naming, environment terminology
# From cluster-info.yaml:
#   platform, version, region, acm.managed
```

## Step 2 — Cluster access verification
Load platform skill from profile (e.g. `platform/rosa-hcp`):
```bash
oc whoami
oc get nodes
oc get --raw /healthz && echo "API OK"
```

## Step 3 — Platform health dimensions
Run checks from `observability/platform-health`:
- [ ] Nodes: all Ready
- [ ] Operators: none Degraded (OCP/ROSA) or kube-system healthy (EKS)
- [ ] Monitoring: Prometheus + Alertmanager running
- [ ] Client workloads: no stuck pods in client namespaces

## Step 4 — ACM compliance (if `acm.managed: true`)
Switch to hub context:
```bash
oc get policies -n open-cluster-management | grep -i [client]
oc get policy [client]-policy-set -n open-cluster-management -o jsonpath='{.status.compliant}'
```
Load `troubleshooting/acm-policies` if NonCompliant.

## Step 5 — SLO and alerting
Load `observability/prometheus`:
```bash
oc get prometheusrule -A | grep [client]
oc get alertmanagerconfig -A | grep [client]
```

## Step 6 — Generate report
Use template from `observability/platform-health`. Save to:
- Onboarding ticket (new engineers)
- Client Confluence (per `profile.docs.style`)
- Incident ticket (post-resolution)

## Pass / Fail Criteria

| Result | Condition |
|--------|-----------|
| **Pass** | All dimensions Green; ACM Compliant or N/A |
| **Warn** | One Yellow dimension; no client workload impact |
| **Fail** | Any Red dimension; open incident per `tasks/incident-response` |

## Common Issues

**Cannot reach hub for ACM checks**
- VPN or context missing — document as "ACM: not checked"
- Do not fail entire health check for hub access alone

**Yellow monitoring on non-critical operator**
- Note in report; create P3 ticket for remediation

## References
- Checks: `observability/platform-health`
- Onboarding: `tasks/client-onboarding` Step 5
- SLOs: `platform-config/slos/[client].yaml`
