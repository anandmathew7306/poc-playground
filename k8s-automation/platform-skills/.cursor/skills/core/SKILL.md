---
name: core
description: >
  Always active. Defines team-wide standards, naming conventions, security gates,
  and the neo stack deploy/observe/runtime contract. Every other skill builds on this.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: core
refs: []
---

# Core Platform Standards

## Team Identity
- Team name: PlatRel
- Repo: platform-skills (skills) | platform-config (IaC) | platform-ops (runbooks)
- Skills library: .cursor/skills/
- Short prompt format: `client: [name] | task: [task-skill] | [optional context]`

## Naming Conventions

### Clusters
[platform]-[client]-[environment]-[region]
Examples:
  rosa-acme-prod-eu-west-1
  eks-globex-nonprod-us-east-1
  ocp-internal-dev-on-prem

### Namespaces
[team]-[service]-[environment]
Examples:
  platform-monitoring-prod
  client-billing-api-prod

### Labels (required on all resources)
```yaml
labels:
  platform.io/client: ""        # client slug
  platform.io/environment: ""   # prod | nonprod | dev
  platform.io/platform: ""      # ocp | rosa | rosa-hcp | eks
  platform.io/managed-by: ""    # helm | kustomize
  platform.io/team: platrel
```

## Security Gates
Before any change reaches production:
- [ ] Image tag is not `latest` — must be SHA or semver
- [ ] No hardcoded secrets — use Sealed Secrets or External Secrets Operator
- [ ] Required labels present on all resources
- [ ] Resource requests and limits defined on all containers
- [ ] NetworkPolicy exists for the namespace
- [ ] Kyverno policy passes in audit before enforce

## Neo Stack Contract

### Deploy Contract
Every service managed by this team must:
- Have a health endpoint at `/healthz` returning HTTP 200 when ready
- Be deployable via Helm chart OR Kustomize base+overlay
- Pin image tags to SHA digest in production
- Declare resource requests and limits

### Observe Contract
Every cluster managed by this team must have:
- OTel collector running as DaemonSet or sidecar
- PrometheusRule for availability SLO recording rule
- Alertmanager route configured for client escalation path
- Grafana dashboard linked in client profile.yaml

### Runtime Contract
Every cluster must enforce:
- Pod Security Standards: restricted for application namespaces
- No privilege escalation
- Read-only root filesystem where possible
- NetworkPolicy: default deny, explicit allow

## How Skills Compose
Task skills reference other skills — they never duplicate content.
When writing a task skill:
  1. State which skills it composes in the refs: frontmatter field
  2. Reference platform/cloud/acm skills for platform-specific steps
  3. Load client profile.yaml for client-specific context
  4. Point to platform-ops/runbooks for troubleshooting steps

## Profile.yaml Resolution
When a client: parameter is provided in the prompt:
  1. Load clients/[client]/profile.yaml from platform-config
  2. Resolve active_skills list
  3. Apply terminology_overrides to all output
  4. Apply doc_style to any documentation output
  5. Use compliance frameworks to gate any changes

## How to Start a New Project
See: tasks/client-onboarding/SKILL.md

## Break-Glass Procedure
For emergency production changes that cannot wait for normal process:
  1. Add annotation to the resource: platform.io/break-glass: "INC-YYYY-NNN"
  2. This bypasses Kyverno enforce policies
  3. A GitHub issue is automatically created by CI
  4. Postmortem required within 48 hours
  5. Policy fix PR required within 5 business days
