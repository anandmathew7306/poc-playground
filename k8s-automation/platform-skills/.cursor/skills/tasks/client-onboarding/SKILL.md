---
name: client-onboarding
description: >
  Use when onboarding a new client or starting work on an existing client project.
  Triggered by: "new client", "start project", "onboard [client name]",
  or "client: [name] | task: client-onboarding".
  Composes platform, cloud, ACM, and observability skills based on profile.yaml.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: tasks
refs:
  - core
  - platform/[resolved from profile]
  - cloud/[resolved from profile]
  - deploy/[resolved from profile]
  - acm/policies
  - observability/prometheus
---

# Client Onboarding

## How This Skill Composes
This skill reads profile.yaml and activates the correct skill chain.
You do not need to know the platform in advance — it is resolved from the profile.

## Step 0 — Before Anything Else
Confirm these inputs exist or create them:

  [ ] platform-config/clients/[client]/profile.yaml  ← REQUIRED
  [ ] platform-config/clusters/[cluster]/cluster-info.yaml
  [ ] platform-config/clusters/[cluster]/contacts.yaml
  [ ] platform-config/slos/[client].yaml
  [ ] platform-skills/.cursor/skills/clients/[client]/SKILL.md

If profile.yaml does not exist:
  → Copy platform-config/clients/_template/profile.yaml
  → Fill every field — do not leave blanks
  → Validate against platform-config/schemas/profile.schema.json
  → Open a PR: "feat: add [client] client profile"
  → Get review before proceeding

## Step 1 — Resolve skill chain from profile.yaml
Read profile.yaml and confirm:
  platform_skill   → load platform/[value]
  cloud_skill      → load cloud/[value]
  deploy_skill     → load deploy/[value]
  compliance       → note frameworks for gate checks throughout
  terminology      → apply overrides to all output from this point

## Step 2 — Cluster access verification
Using the resolved platform skill:

```bash
# Verify cluster access
oc whoami
oc cluster-info

# Verify you are on the correct cluster
oc get clusterversion
oc get infrastructure cluster -o jsonpath='{.status.platform}'

# Verify required labels exist
oc get namespaces -l platform.io/client=[client]
```

## Step 3 — ACM registration check
Load: acm/policies skill
Load: acm/placement skill

```bash
# Verify cluster is registered with ACM hub
oc get managedcluster [cluster-name]

# Verify placement matches this cluster
oc get placement [client]-placement -n open-cluster-management

# Verify policy set is applied
oc get policyset [client]-policy-set -n open-cluster-management
```

## Step 4 — Observability baseline
Load: observability/prometheus skill

```bash
# Verify user workload monitoring is enabled
oc get configmap cluster-monitoring-config -n openshift-monitoring -o yaml

# Verify SLO recording rules are deployed
oc get prometheusrule -n openshift-monitoring | grep [client]

# Verify Alertmanager route exists for client
oc get alertmanagerconfig -A | grep [client]
```

## Step 5 — Run platform health check
Load: tasks/platform-health-check skill
Run full health check and save output.

## Step 6 — Create client documentation
Using profile.yaml doc_style field:

If doc_style = confluence:
  Create pages using Confluence format
  Required pages:
    - Platform Overview (cluster-info.yaml as source)
    - Runbook Index (links to platform-ops/runbooks/)
    - SLO Dashboard (links to Grafana)
    - Contacts and Escalation

If doc_style = github-wiki:
  Create markdown pages in client's wiki
  Same required pages as above

## Step 7 — Handover checklist
  [ ] profile.yaml complete and reviewed
  [ ] cluster-info.yaml complete
  [ ] contacts.yaml complete with verified contact details
  [ ] SLO definition deployed and recording rules verified
  [ ] Alertmanager route tested (send test alert)
  [ ] ACM policies applied and compliant
  [ ] Platform health check passed
  [ ] Documentation created in client's tool
  [ ] Runbook index created with links
  [ ] Client contacts have been shown the escalation process

## Common Issues During Onboarding
→ See: troubleshooting/ocp-operators (if operators not ready)
→ See: troubleshooting/acm-policies (if policies non-compliant)
→ See: runbooks/acm/policy-noncompliant.md
