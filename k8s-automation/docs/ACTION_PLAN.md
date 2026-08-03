# k8s-automation

# AI-First Platform Team — Action Plan
## Complete repo structure, milestones, and cursor agent instructions

---

## HOW TO USE THIS DOCUMENT

Paste each milestone block directly into Cursor agent.
Each block is self-contained and tells the agent exactly what to create.
Work through milestones in order — each builds on the previous.

---

## MILESTONE 1: Bootstrap the three core repos

**Paste this into Cursor agent:**

```
Create the following three Git repositories with this exact structure.
Initialise each with a README.md and .gitignore. Do not add any other files yet.

Repo 1: platform-skills
  Purpose: AI skill library — teaches the agent how the team works
  Visibility: private
  Default branch: main

Repo 2: platform-config
  Purpose: actual IaC — cluster configs, RHACM policies, Kustomize bases
  Visibility: private
  Default branch: main

Repo 3: platform-ops
  Purpose: runbooks, SLOs, postmortems, SOPs
  Visibility: private
  Default branch: main

For each repo create:
  README.md       — one paragraph explaining the repo purpose
  .gitignore      — appropriate for a GitOps/Kubernetes project
  CODEOWNERS      — placeholder with comment explaining usage
  CONTRIBUTING.md — placeholder with comment explaining usage

Commit message: "chore: bootstrap repo structure"
```

---

## MILESTONE 2: platform-skills — full skeleton

**Paste this into Cursor agent:**

```
In the platform-skills repo, create the following complete directory and file structure.
Every SKILL.md must include valid YAML frontmatter and a placeholder body.
Do not fill in technical content yet — structure and frontmatter only.

Root files:
  CONSTITUTION.md
  governance/
    allowed-skills.sha256
    skill-review-checklist.md
  docs/
    platform-matrix.md
    onboarding-bootcamp.md

Skill directories — each must contain a SKILL.md:

  .cursor/skills/
    core/
      SKILL.md
    platform/
      ocp/
        SKILL.md
      rosa/
        SKILL.md
      rosa-hcp/
        SKILL.md
      eks/
        SKILL.md
    cloud/
      aws/
        SKILL.md
      azure/
        SKILL.md    ← stub only, not active yet
    acm/
      policies/
        SKILL.md
      placement/
        SKILL.md
    cicd/
      gitlab/
        SKILL.md
    observability/
      prometheus/
        SKILL.md
      platform-health/
        SKILL.md
      otel/
        SKILL.md    ← stub only
      logging/
        SKILL.md    ← stub only
    troubleshooting/
      ocp-nodes/
        SKILL.md
      ocp-operators/
        SKILL.md
      acm-policies/
        SKILL.md
      network/
        SKILL.md
    tasks/
      incident-response/
        SKILL.md
      platform-health-check/
        SKILL.md
      policy-authoring/
        SKILL.md
      client-onboarding/
        SKILL.md

Every SKILL.md must use this exact frontmatter format:
---
name: [skill-name]
description: >
  Use when [specific trigger condition].
  Covers [key topics this skill addresses].
status: active        # active | stub | deprecated
reviewed_at: ""       # fill when first real content is added
version: 0.1.0
layer: [core|platform|cloud|acm|cicd|observability|troubleshooting|tasks]
refs: []              # list of other skill names this skill composes
---

# [Skill Name]

## When to Use
[placeholder]

## Key Concepts
[placeholder]

## Commands and Patterns
[placeholder]

## Common Issues
[placeholder]

## References
[placeholder]

Commit message: "chore: scaffold full skill library structure"
```

---

## MILESTONE 3: platform-config — full skeleton

**Paste this into Cursor agent:**

```
In the platform-config repo, create the following directory structure.
Add placeholder files where indicated. This is the IaC layer — cluster configs,
RHACM policies, Kustomize bases.

Directory structure:

  clusters/
    _template/
      cluster-info.yaml     ← schema template, see spec below
      contacts.yaml         ← schema template, see spec below

  clients/
    _template/
      profile.yaml          ← canonical schema, see spec below
      kustomize/
        kustomization.yaml  ← placeholder
      policies/
        kustomization.yaml  ← placeholder

  base/
    ocp/
      kustomization.yaml
      namespaces/
        kustomization.yaml
      rbac/
        kustomization.yaml
      operators/
        kustomization.yaml
    rosa/
      kustomization.yaml
    eks/
      kustomization.yaml

  acm/
    policies/
      kustomization.yaml
      README.md             ← note: sourced from policy-collection, see refs
    placements/
      kustomization.yaml
    policy-sets/
      kustomization.yaml

  slos/
    _template.yaml          ← SLO schema template

  schemas/
    profile.schema.json     ← JSON Schema for profile.yaml validation
    cluster-info.schema.json


--- cluster-info.yaml schema ---
Create clusters/_template/cluster-info.yaml with this exact structure:

apiVersion: platform.io/v1
kind: ClusterInfo
metadata:
  name: ""                    # cluster name
  environment: ""             # prod | nonprod | dev
spec:
  platform: ""                # ocp | rosa | rosa-hcp | eks
  version: ""                 # platform version e.g. 4.15
  region: ""                  # aws region or datacenter
  cloud: ""                   # aws | azure | on-prem
  addons: []                  # list of installed add-ons
  acm:
    managed: false            # is this cluster managed by ACM?
    hub: false                # is this the ACM hub cluster?
  skills:
    platform_skill: ""        # which platform skill applies e.g. platform/rosa-hcp
    cloud_skill: ""           # which cloud skill applies e.g. cloud/aws
  notes: ""


--- contacts.yaml schema ---
Create clusters/_template/contacts.yaml with this exact structure:

apiVersion: platform.io/v1
kind: ClusterContacts
metadata:
  name: ""
spec:
  client: ""
  primary_contact:
    name: ""
    email: ""
    slack: ""
  escalation:
    - level: 1
      contact: ""
      method: ""            # slack | pagerduty | phone
    - level: 2
      contact: ""
      method: ""
  oncall:
    schedule: ""            # link to PagerDuty/OpsGenie schedule
    sla:
      p1_response: ""       # e.g. 30m
      p2_response: ""       # e.g. 4h
      p3_response: ""       # e.g. next business day


--- profile.yaml schema ---
Create clients/_template/profile.yaml with this exact structure:

apiVersion: platform.io/v1
kind: ClientProfile
metadata:
  name: ""                    # client slug e.g. acme
  created_at: ""
  updated_at: ""
spec:
  # --- Identity ---
  display_name: ""            # human readable client name
  description: ""             # one line about what they do

  # --- Platform ---
  platform: ""                # ocp | rosa | rosa-hcp | eks
  platform_skill: ""          # refs: platform/rosa-hcp
  cloud: ""                   # aws | azure | on-prem
  cloud_skill: ""             # refs: cloud/aws
  deploy_tool: ""             # helm | kustomize | both
  deploy_skill: ""            # refs: deploy/kustomize

  # --- ACM ---
  acm:
    managed: false
    policy_set: ""            # name of their PolicySet
    placement: ""             # name of their Placement resource

  # --- SRE ---
  sre:
    slo_file: ""              # path to their SLO definition
    alerting: ""              # pagerduty | opsgenie | email
    observability_skill: ""   # refs: observability/prometheus
    dashboard_url: ""

  # --- Documentation ---
  docs:
    style: ""                 # confluence | notion | github-wiki | gdocs
    space_url: ""             # link to their doc space
    runbook_path: ""          # path in platform-ops/runbooks/

  # --- Compliance ---
  compliance:
    frameworks: []            # SOC2 | PCI | ISO27001 | FedRAMP | none
    data_classification: ""   # public | internal | confidential | restricted
    audit_logging: false

  # --- Terminology ---
  terminology:
    environment_names:        # what they call environments
      prod: ""                # e.g. "production" or "live"
      nonprod: ""             # e.g. "staging" or "uat"
    cluster_naming: ""        # their cluster naming convention
    ticket_prefix: ""         # e.g. ACME for JIRA tickets

  # --- Skills composition ---
  # These are resolved automatically when a task skill loads this profile
  active_skills:
    - ""                      # list of all skills relevant to this client


--- slos/_template.yaml ---
Create with this structure:

apiVersion: platform.io/v1
kind: SLODefinition
metadata:
  name: ""
  client: ""
spec:
  services:
    - name: ""
      slos:
        - name: availability
          target: 99.9
          window: 30d
          indicator:
            type: request_based
            good_events: ""   # PromQL
            total_events: ""  # PromQL
        - name: latency
          target: 95.0        # 95% of requests under threshold
          threshold_ms: 500
          window: 30d

Commit message: "chore: scaffold platform-config structure with schemas"
```

---

## MILESTONE 4: platform-ops — full skeleton

**Paste this into Cursor agent:**

```
In the platform-ops repo, create the following structure.
This is the operational knowledge layer — runbooks, postmortems, SOPs.

Directory structure:

  runbooks/
    _template.md              ← runbook template, see spec below
    ocp/
      node-notready.md        ← populate with template, add placeholder content
      operator-degraded.md
      mco-stuck.md
      etcd-unhealthy.md
    rosa/
      sts-auth-failure.md
      managed-addon-degraded.md
    rosa-hcp/
      hostedcluster-degraded.md
      nodepool-unavailable.md
    eks/
      node-notready.md
      addon-degraded.md
    acm/
      policy-noncompliant.md
      placement-not-matching.md
      hub-degraded.md
    observability/
      prometheus-down.md
      alertmanager-silenced.md
      scrape-target-down.md
    network/
      ovn-pod-connectivity.md
      dns-resolution-failure.md
      egress-ip-not-working.md

  postmortems/
    _template.md              ← postmortem template, see spec below
    README.md                 ← explains blameless postmortem culture

  sops/
    cluster-upgrade.md        ← Standard Operating Procedure template
    client-offboarding.md
    access-provisioning.md
    certificate-rotation.md

  incidents/
    README.md                 ← explains incident lifecycle

  slos/
    README.md                 ← explains SLO review process


--- runbooks/_template.md ---
Create with this exact format. Every runbook must follow this structure:

---
title: ""
platform: ""          # ocp | rosa | rosa-hcp | eks | acm | all
severity: ""          # P1 | P2 | P3
last_updated: ""
last_tested: ""
author: ""
---

# [Alert/Issue Name]

## Symptom
What the engineer sees — alert text, error message, or observable behaviour.

## Impact
What breaks for the client if this is not resolved.

## Quick Checks
Run these first — in this order:

```bash
# 1. Check [what]
oc get [resource] -n [namespace]

# 2. Check [what]
oc describe [resource] [name] -n [namespace]

# 3. Check [what]
oc logs [pod] -n [namespace] --tail=50
```

## Common Causes

### Cause 1: [Name]
**Symptoms:** what makes you think this is the cause
**Fix:**
```bash
[commands]
```

### Cause 2: [Name]
**Symptoms:**
**Fix:**
```bash
[commands]
```

## Escalation Criteria
Escalate to next level if:
- [ ] [condition]
- [ ] [condition]
- [ ] More than [X] minutes elapsed without progress

## Related
- Skill: [which skill covers this]
- Runbook: [related runbooks]
- Dashboard: [relevant Grafana dashboard]

## Change Log
| Date | Author | Change |
|------|--------|--------|
| | | Initial version |


--- postmortems/_template.md ---
Create with this exact format:

---
incident_id: ""         # INC-YYYY-NNN
date: ""
severity: ""            # P1 | P2
duration: ""            # e.g. 47 minutes
author: ""
reviewers: []
status: draft           # draft | reviewed | closed
---

# Postmortem: [Short Title]

## Summary
One paragraph. What happened, what broke, how it was resolved.

## Timeline
| Time | Event |
|------|-------|
| HH:MM | Alert fired |
| HH:MM | Engineer paged |
| HH:MM | [key diagnostic step] |
| HH:MM | Root cause identified |
| HH:MM | Fix applied |
| HH:MM | Service restored |

## Root Cause
[Detailed explanation. No blame. Focus on the system condition that allowed this to happen.]

## Impact
- Duration of impact:
- Clients affected:
- SLO impact:

## What Went Well
- [thing]

## What Went Wrong
- [thing]

## Action Items
| Action | Owner | Due | PR/Issue |
|--------|-------|-----|----------|
| Update runbook for [X] | @name | [date] | |
| Update skill [X] | @name | [date] | |
| Fix [root cause] | @name | [date] | |

## Lessons Learned
[What does this teach us about the system or our process?]

Commit message: "chore: scaffold platform-ops structure with templates"
```

---

## MILESTONE 5: Fill core/SKILL.md — the foundation every other skill references

**Paste this into Cursor agent:**

```
In platform-skills, fill .cursor/skills/core/SKILL.md with the following content.
This is the most important skill — it defines team-wide standards.
Replace all [bracketed] values with the team's actual values.

---
name: core
description: >
  Always active. Defines team-wide standards, naming conventions, security gates,
  and the neo stack deploy/observe/runtime contract. Every other skill builds on this.
status: active
reviewed_at: [today's date]
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

Commit message: "feat: fill core skill with team standards"
```

---

## MILESTONE 6: Mock client end-to-end — Acme Corp

**Paste this into Cursor agent:**

```
Create a complete mock client called "acme" across all three repos.
This is the reference example the team uses to understand the full system.
Use realistic but fictional data.

--- IN platform-config ---

Create clients/acme/profile.yaml:

apiVersion: platform.io/v1
kind: ClientProfile
metadata:
  name: acme
  created_at: "2026-01-15"
  updated_at: "2026-06-01"
spec:
  display_name: Acme Corporation
  description: E-commerce platform running on ROSA HCP, AWS, SOC2 compliant

  platform: rosa-hcp
  platform_skill: platform/rosa-hcp
  cloud: aws
  cloud_skill: cloud/aws
  deploy_tool: kustomize
  deploy_skill: deploy/kustomize

  acm:
    managed: true
    policy_set: acme-policy-set
    placement: acme-placement

  sre:
    slo_file: slos/acme.yaml
    alerting: pagerduty
    observability_skill: observability/prometheus
    dashboard_url: https://grafana.example.com/d/acme

  docs:
    style: confluence
    space_url: https://acme.atlassian.net/wiki/spaces/PLATFORM
    runbook_path: platform-ops/runbooks/

  compliance:
    frameworks:
      - SOC2
    data_classification: confidential
    audit_logging: true

  terminology:
    environment_names:
      prod: production
      nonprod: staging
    cluster_naming: acme-[env]-[region]
    ticket_prefix: ACME

  active_skills:
    - core
    - platform/rosa-hcp
    - cloud/aws
    - deploy/kustomize
    - acm/policies
    - observability/prometheus
    - troubleshooting/ocp-nodes
    - troubleshooting/ocp-operators


Create clusters/acme-prod/cluster-info.yaml:

apiVersion: platform.io/v1
kind: ClusterInfo
metadata:
  name: acme-prod
  environment: prod
spec:
  platform: rosa-hcp
  version: "4.15"
  region: eu-west-1
  cloud: aws
  addons:
    - aws-ebs-csi-driver
    - aws-load-balancer-controller
    - openshift-gitops
  acm:
    managed: true
    hub: false
  skills:
    platform_skill: platform/rosa-hcp
    cloud_skill: cloud/aws
  notes: Production cluster. SOC2 scope. No direct SSH access.


Create clusters/acme-prod/contacts.yaml:

apiVersion: platform.io/v1
kind: ClusterContacts
metadata:
  name: acme-prod
spec:
  client: acme
  primary_contact:
    name: Jane Smith
    email: jane.smith@acme.example.com
    slack: "@jane-acme"
  escalation:
    - level: 1
      contact: jane.smith@acme.example.com
      method: slack
    - level: 2
      contact: cto@acme.example.com
      method: phone
  oncall:
    schedule: https://pagerduty.example.com/schedules/acme
    sla:
      p1_response: 30m
      p2_response: 4h
      p3_response: next business day


Create slos/acme.yaml:

apiVersion: platform.io/v1
kind: SLODefinition
metadata:
  name: acme-slos
  client: acme
spec:
  services:
    - name: api-gateway
      slos:
        - name: availability
          target: 99.9
          window: 30d
          indicator:
            type: request_based
            good_events: |
              sum(rate(http_requests_total{job="api-gateway",code!~"5.."}[5m]))
            total_events: |
              sum(rate(http_requests_total{job="api-gateway"}[5m]))
        - name: latency
          target: 95.0
          threshold_ms: 500
          window: 30d


Create clients/acme/kustomize/kustomization.yaml:

apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: acme-prod
bases:
  - ../../base/rosa


Create clients/acme/policies/kustomization.yaml:

apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../../acm/policies


--- IN platform-skills ---

Create .cursor/skills/clients/acme/SKILL.md:

---
name: acme-client
description: >
  Use when working on any task for client Acme Corporation.
  Loads Acme-specific terminology, compliance requirements (SOC2),
  documentation style (Confluence), and active skill set.
  Always load this before any task skill when client is acme.
status: active
reviewed_at: "2026-06-01"
version: 1.0.0
layer: clients
refs:
  - core
  - platform/rosa-hcp
  - cloud/aws
  - deploy/kustomize
  - acm/policies
  - observability/prometheus
---

# Acme Client Overlay

## Profile
Load from: platform-config/clients/acme/profile.yaml

## Platform Context
- Platform: ROSA with Hosted Control Planes (Hypershift)
- Cloud: AWS eu-west-1 (prod), eu-west-2 (dr)
- Deploy tool: Kustomize
- ACM hub cluster: hub-prod (separate cluster)

## Compliance Context
- SOC2 Type II in scope
- All changes require audit log entry
- No direct cluster access without ticket reference
- Data classification: confidential — no client data in logs or error messages

## Terminology
| Generic term | Acme term |
|--------------|-----------|
| production | production (never "prod" in client-facing docs) |
| nonprod | staging |
| cluster upgrade | platform maintenance window |
| incident | service event |

## Documentation Style
- Tool: Confluence
- Space: https://acme.atlassian.net/wiki/spaces/PLATFORM
- Format: every runbook page must have: Summary, Steps, Rollback, Sign-off table
- Tone: formal, no jargon in executive summaries

## Escalation
- P1: page PagerDuty immediately, notify jane.smith@acme.example.com within 15 min
- All changes to production require ACME-prefixed ticket reference

## Contacts
See: platform-config/clusters/acme-prod/contacts.yaml


--- IN platform-ops ---

Create runbooks/rosa-hcp/hostedcluster-degraded.md
using the runbook template format from Milestone 4.
Populate with realistic placeholder content for a ROSA HCP degraded scenario:
- Symptom: HostedCluster shows status Degraded
- Quick checks: oc get hostedcluster, oc describe hostedcluster, check NodePool
- Two common causes: NodePool capacity issue, AWS quota exceeded
- Escalation: if not resolved in 30 min, escalate to Red Hat support

Commit message: "feat: add acme mock client end-to-end example"
```

---

## MILESTONE 7: How to start a new project — the client-onboarding task skill

**Paste this into Cursor agent:**

```
In platform-skills, fill .cursor/skills/tasks/client-onboarding/SKILL.md
with complete content. This skill defines the exact process for starting
any new client project. It composes other skills — it does not duplicate them.

---
name: client-onboarding
description: >
  Use when onboarding a new client or starting work on an existing client project.
  Triggered by: "new client", "start project", "onboard [client name]",
  or "client: [name] | task: client-onboarding".
  Composes platform, cloud, ACM, and observability skills based on profile.yaml.
status: active
reviewed_at: [today's date]
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

Commit message: "feat: fill client-onboarding task skill"
```

---

## MILESTONE 8: CI pipeline — skill security and validation

**Paste this into Cursor agent:**

```
In platform-skills, create .github/workflows/skill-ci.yaml with the following
content. This pipeline runs on every PR that touches .cursor/skills/.

Create .github/workflows/skill-ci.yaml:

name: Skill CI

on:
  pull_request:
    paths:
      - '.cursor/skills/**'
      - 'governance/**'

jobs:
  validate-frontmatter:
    name: Validate SKILL.md frontmatter
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check required frontmatter fields
        run: |
          find .cursor/skills -name "SKILL.md" | while read f; do
            python3 scripts/validate-frontmatter.py "$f"
          done

  security-scan-content:
    name: Semgrep scan on SKILL.md content
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: returntocorp/semgrep-action@v1
        with:
          config: .semgrep/skill-rules.yaml

  security-scan-scripts:
    name: Snyk scan on bundled scripts
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Scan scripts in skill directories
        run: |
          find .cursor/skills -name "*.sh" -o -name "*.py" | \
          xargs snyk test --file={} || true

  allowlist-check:
    name: External skill allowlist check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Verify no external URLs outside allowlist
        run: |
          python3 scripts/check-allowlist.py


Also create scripts/validate-frontmatter.py:

#!/usr/bin/env python3
import sys
import yaml

REQUIRED_FIELDS = ['name', 'description', 'status', 'layer']

def validate(filepath):
    with open(filepath) as f:
        content = f.read()
    if not content.startswith('---'):
        print(f"FAIL {filepath}: missing frontmatter")
        sys.exit(1)
    parts = content.split('---', 2)
    if len(parts) < 3:
        print(f"FAIL {filepath}: malformed frontmatter")
        sys.exit(1)
    fm = yaml.safe_load(parts[1])
    for field in REQUIRED_FIELDS:
        if field not in fm or not fm[field]:
            print(f"FAIL {filepath}: missing required field '{field}'")
            sys.exit(1)
    print(f"OK   {filepath}")

if __name__ == '__main__':
    validate(sys.argv[1])


Also create .semgrep/skill-rules.yaml:

rules:
  - id: skill-credential-exfil
    patterns:
      - pattern-either:
          - pattern: |
              $...SSH_KEY.../.ssh...
          - pattern: |
              $...AWS_SECRET...
          - pattern: |
              $...curl.*webhook...
          - pattern: |
              $...base64.*decode.*exec...
    message: |
      Potential credential exfiltration in SKILL.md.
      Review carefully before merging.
    languages: [generic]
    severity: ERROR
    paths:
      include:
        - "**/*.md"

  - id: skill-prompt-injection
    patterns:
      - pattern-either:
          - pattern: |
              ignore previous instructions
          - pattern: |
              override safety
          - pattern: |
              disregard your
    message: Potential prompt injection attempt in skill content.
    languages: [generic]
    severity: ERROR
    paths:
      include:
        - "**/*.md"

  - id: skill-curl-bash
    pattern: |
      curl $URL | bash
    message: curl-pipe-bash is prohibited in skills.
    languages: [generic]
    severity: ERROR


Also create .github/workflows/release.yaml:

name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate changelog
        run: |
          git log $(git describe --tags --abbrev=0 HEAD^)..HEAD \
            --pretty=format:"- %s" > CHANGELOG_ENTRY.md
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          body_path: CHANGELOG_ENTRY.md
          files: |
            CHANGELOG_ENTRY.md

Commit message: "feat: add skill CI pipeline and security scanning"
```

---

## MILESTONE 9: App repo integration — how a project consumes the skills

**Paste this into Cursor agent:**

```
Create a reference example showing how a client application repo
consumes platform-skills. Create this as a standalone directory
called example-app-repo/ in platform-skills with the following structure.

This is the pattern every application repo must follow.

example-app-repo/
  README.md             ← explains how skills are consumed
  .gitmodules           ← submodule pointing to platform-skills
  .cursor/
    skills/             ← symlink or submodule target
  scripts/
    init-skills.sh      ← one-time setup script

Create .gitmodules:
[submodule "platform-skills"]
  path = .cursor/skills
  url = git@github.com:[org]/platform-skills.git
  branch = main

Create scripts/init-skills.sh:
#!/bin/bash
# Run once after cloning a new project repo
# Pins skills to the approved release tag

SKILLS_TAG=${1:-"v1.0.0"}

echo "Initialising platform-skills at tag $SKILLS_TAG"

git submodule add \
  git@github.com:[org]/platform-skills.git \
  .cursor/skills

cd .cursor/skills
git checkout tags/$SKILLS_TAG
cd ../..

git add .gitmodules .cursor/skills
git commit -m "chore: pin platform-skills to $SKILLS_TAG"

echo "Done. Skills available at .cursor/skills/"
echo "Run 'git submodule update --init' after cloning on any new machine."

Create example-app-repo/README.md explaining:
1. This repo uses platform-skills for AI-assisted development
2. Skills are pinned to a specific release tag via git submodule
3. To start working on a client task, use the short prompt format:
   client: acme | task: [task-name] | [optional context]
4. To update skills to a new version:
   cd .cursor/skills && git checkout tags/vX.Y.Z && cd ../.. && git add .cursor/skills && git commit

Commit message: "docs: add example app repo integration pattern"
```

---

## MILESTONE 10: CONSTITUTION.md and team agreement

**Paste this into Cursor agent:**

```
In platform-skills, create CONSTITUTION.md with the following content.
This is the non-negotiable team agreement. Every team member must read
and acknowledge this before contributing.

---

# Platform Skills Constitution

## The Three Laws

### Law 1: If it is not in Git, it does not exist
Every decision, pattern, runbook, client detail, and tribal knowledge item
must live in one of the three platform repos.
Slack messages are not documentation. Memory is not documentation.

### Law 2: Task skills compose — they never duplicate
A task skill references other skills by name in its refs: frontmatter field.
It never copies content from a platform, cloud, ACM, or observability skill.
If you find yourself writing OCP-specific commands in a task skill, stop —
put them in platform/ocp/SKILL.md and reference it.

### Law 3: Every incident improves the system
Within 48 hours of closing an incident:
- A runbook exists or is updated in platform-ops
- If the agent lacked context, a skill is updated in platform-skills
- If config was wrong, a PR is open in platform-config

## The Skill Security Compact
- Zero external skills without SHA pin and human review
- No skill with allowed-tools: bash or network merges without two approvals
- Semgrep and Snyk must pass before any skill PR merges
- Review the governance/skill-review-checklist.md for every external skill

## The Profile.yaml Contract
- A client profile must exist before any work begins on that client
- Profile is the source of truth — if reality differs from profile, update the profile
- All active_skills must be listed — incomplete profiles are rejected in CI

## How We Make Decisions
- Platform standards: any team member proposes via PR, any team member can approve
- Security policies: require two approvals
- Client profiles: require approval from client anchor (the team member who owns that relationship)
- External skills: require two approvals + semgrep/snyk pass + entry in allowed-skills.sha256

## What We Measure
Every two weeks we review:
- Time to onboard last client (target: < 2 weeks)
- P1 MTTR (target: < 30 minutes)
- Skills with reviewed_at > 90 days old (target: zero)
- Incidents without a runbook PR within 48h (target: zero)

## Anti-Patterns We Refuse
- Snowflake client setups that bypass the golden path
- Skills written speculatively for platforms we don't operate yet
- Runbooks that live anywhere except platform-ops
- Merging on main without a PR
- Any direct change to a production cluster without a ticket reference

Commit message: "docs: add team constitution"
```

---

## DAILY WORKFLOW — paste this card somewhere visible

```
STARTING WORK ON A CLIENT:
  client: [name] | task: client-onboarding

RUNNING A HEALTH CHECK:
  client: [name] | task: platform-health-check

RESPONDING TO AN INCIDENT:
  client: [name] | task: incident-response | alert: [alert name]

AUTHORING A NEW RHACM POLICY:
  client: [name] | task: policy-authoring | policy: [what it enforces]

CLOSING AN INCIDENT (required steps):
  1. Fix is confirmed
  2. Open runbook PR in platform-ops (use template)
  3. If skill was wrong or missing, open PR in platform-skills
  4. Link both PRs to the incident ticket
  5. Close incident

ADDING A NEW CLIENT:
  1. Copy platform-config/clients/_template/profile.yaml
  2. Fill every field
  3. Validate: python3 scripts/validate-frontmatter.py
  4. Create .cursor/skills/clients/[client]/SKILL.md
  5. PR both, get review
  6. Run: client: [name] | task: client-onboarding
```

---

## MILESTONE ORDER SUMMARY

| # | Milestone | Outcome |
|---|-----------|---------|
| 1 | Bootstrap three repos | Repos exist with correct structure |
| 2 | platform-skills skeleton | All skill directories and frontmatter exist |
| 3 | platform-config skeleton | All IaC directories and schemas exist |
| 4 | platform-ops skeleton | All runbook templates and directories exist |
| 5 | Fill core/SKILL.md | Team standards encoded, all other skills can reference it |
| 6 | Acme mock client | End-to-end example the team can clone and run |
| 7 | client-onboarding task skill | Complete new project workflow defined |
| 8 | CI pipeline | Skill security automated, no manual policing |
| 9 | App repo integration | Any project can consume skills via submodule |
| 10 | CONSTITUTION.md | Team agreement in writing, habits defined |

**After Milestone 10:** fill skill content reactively — one real task or incident at a time.
The structure is done. The content grows from real work.
