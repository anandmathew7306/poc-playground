---
name: tasks/incident-response
description: >
  Use when responding to a production incident or alert.
  Covers triage, escalation, runbook execution, and post-incident closure.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: tasks
refs:
  - core
  - observability/prometheus
  - observability/platform-health
---

# Tasks/Incident Response

## When to Use
- PagerDuty/OpsGenie page or client-reported outage
- Prompt: `client: [name] | task: incident-response | alert: [alert name]`
- Any P1/P2 production issue requiring structured response

## How This Skill Composes
1. Load `clients/[client]/SKILL.md` and `profile.yaml` for terminology and escalation
2. Load platform skill from `profile.spec.platform_skill`
3. Find matching runbook in `platform-ops/runbooks/`
4. Use troubleshooting skills — do not duplicate their commands here

## Incident Workflow

### 1. Acknowledge and classify
- Acknowledge page within client SLA (see `contacts.yaml` → `oncall.sla`)
- Severity: P1 (outage), P2 (degraded), P3 (minor)
- Create ticket: `[TICKET_PREFIX]-[number]` from client profile

### 2. Load context
```bash
# Confirm correct cluster
oc whoami
oc get infrastructure cluster -o jsonpath='{.status.platform}{"\n"}' 2>/dev/null || kubectl cluster-info

# Load contacts
# platform-config/clusters/[cluster]/contacts.yaml
```

### 3. Triage — run Quick Checks from runbook
- Match alert name to runbook: `platform-ops/runbooks/[platform]/[issue].md`
- Execute Quick Checks section in order
- Document findings in incident ticket

### 4. Escalate per criteria
- Runbook "Escalation Criteria" section
- Client contacts: `contacts.yaml` escalation levels
- Red Hat support: ROSA/OCP clusters with active subscription
- P1: notify primary contact within 15 min (Acme: jane.smith@acme.example.com)

### 5. Mitigate and communicate
- Prefer GitOps fix via PR; break-glass only with `platform.io/break-glass: INC-YYYY-NNN`
- Status updates every 30 min for P1, every 2h for P2
- Use client terminology (e.g. Acme: "service event" not "incident" in client comms)

### 6. Resolve and close
- [ ] Fix confirmed — run `tasks/platform-health-check`
- [ ] Runbook PR opened in platform-ops within 48h
- [ ] Skill updated in platform-skills if agent lacked context
- [ ] Postmortem for P1/P2: `platform-ops/postmortems/_template.md`
- [ ] Link PRs to incident ticket; close incident

## Common Issues

**Wrong cluster context**
- `oc config current-context` — switch before any changes
- Cluster name must match `cluster-info.yaml`

**Alert name doesn't match runbook**
- Search: `grep -r "[alert-keyword]" platform-ops/runbooks/`
- Fall back to platform troubleshooting skill by symptom

**Break-glass needed**
- Follow `core` break-glass procedure
- Postmortem mandatory within 48h

## References
- Health verification: `tasks/platform-health-check`
- Contacts: `platform-config/clusters/*/contacts.yaml`
- Postmortems: `platform-ops/postmortems/`
- Constitution Law 3: every incident improves the system
