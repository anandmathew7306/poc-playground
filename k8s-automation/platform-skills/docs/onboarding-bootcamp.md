# Onboarding Bootcamp

Four-week onboarding guide for new PlatRel engineers. Each week builds on the three-repo model: **platform-skills** (how the agent and team work), **platform-config** (IaC and client profiles), **platform-ops** (runbooks and SLOs).

## Prerequisites (Day 0)

- [ ] GitLab access to all three repos
- [ ] AWS console read access (eu-west-1 minimum)
- [ ] `oc`, `kubectl`, `aws`, `kustomize` CLI installed
- [ ] Cursor IDE with platform-skills cloned locally
- [ ] Read `CONSTITUTION.md` and acknowledge in onboarding ticket

## Week 1 — Foundations

**Goal:** Understand the three-repo model and run your first agent-assisted task.

| Day | Activity | Repo |
|-----|----------|------|
| 1 | Read `core/SKILL.md`, `docs/platform-matrix.md`, `CONSTITUTION.md` | platform-skills |
| 2 | Explore `clients/_template/profile.yaml` and `schemas/profile.schema.json` | platform-config |
| 3 | Read `runbooks/_template.md` and one completed runbook (`rosa-hcp/hostedcluster-degraded.md`) | platform-ops |
| 4 | Study the Acme mock client: `clients/acme/profile.yaml`, `clusters/acme-prod/`, `clients/acme/SKILL.md` | all three |
| 5 | Run prompt: `client: acme | task: client-onboarding` in Cursor; document what skills loaded | platform-skills |

**Deliverable:** Short write-up (Confluence or MR comment) explaining how skills compose via `refs` and `profile.yaml`.

## Week 2 — Platform Operations

**Goal:** Hands-on cluster access and health checks on a nonprod cluster.

| Day | Activity | Repo |
|-----|----------|------|
| 1 | Complete platform skill for your assigned platform (`platform/rosa-hcp` or `platform/eks`) | platform-skills |
| 2 | Log into nonprod cluster; run `oc whoami`, `oc get nodes`, `oc get co` | live cluster |
| 3 | Run `client: acme | task: platform-health-check`; compare output to skill steps | platform-skills |
| 4 | Trace an alert path: PrometheusRule → Alertmanager → PagerDuty in `observability/prometheus` skill | platform-skills |
| 5 | Pair with on-call engineer: shadow one P3 alert triage using a runbook | platform-ops |

**Deliverable:** Platform health check output saved to onboarding ticket; one runbook improvement PR (typos or missing command).

## Week 3 — GitOps and ACM

**Goal:** Make a safe, reviewed change through the GitOps pipeline.

| Day | Activity | Repo |
|-----|----------|------|
| 1 | Read `deploy/kustomize` and `acm/policies` skills | platform-skills |
| 2 | Explore `base/rosa/`, `clients/acme/kustomize/`, `acm/policies/` | platform-config |
| 3 | Run `kustomize build clients/acme/kustomize/` locally; understand overlay pattern | platform-config |
| 4 | Read `tasks/policy-authoring` skill; review one Kyverno policy in `acm/policies/` | platform-skills |
| 5 | Open a docs-only PR: add a label example or fix a skill command | platform-skills |

**Deliverable:** Merged docs PR; `kustomize build` output attached to ticket.

## Week 4 — Incidents and Ownership

**Goal:** Respond to a simulated incident end-to-end.

| Day | Activity | Repo |
|-----|----------|------|
| 1 | Read `tasks/incident-response` and `troubleshooting/` skills for your platform | platform-skills |
| 2 | Tabletop exercise: HostedCluster Degraded scenario using `platform-ops/runbooks/rosa-hcp/hostedcluster-degraded.md` | platform-ops |
| 3 | Practice escalation: find contacts in `clusters/acme-prod/contacts.yaml` | platform-config |
| 4 | Draft a postmortem from `postmortems/_template.md` for the tabletop | platform-ops |
| 5 | Onboarding review with mentor: demo `client: [name] | task: [task]` prompt format | all three |

**Deliverable:** Tabletop postmortem draft; mentor sign-off on onboarding checklist.

## Ongoing Expectations

- **Prompt format:** `client: [name] | task: [task-skill] | [context]`
- **Every incident:** runbook PR within 48h; skill update if agent lacked context
- **Skill freshness:** `reviewed_at` must not exceed 90 days — see `governance/skill-review-checklist.md`
- **No snowflakes:** new clients follow `tasks/client-onboarding`; copy Acme pattern

## Quick Reference

| I need to… | Start here |
|------------|------------|
| Onboard a client | `tasks/client-onboarding/SKILL.md` |
| Run health check | `tasks/platform-health-check/SKILL.md` |
| Respond to alert | `tasks/incident-response/SKILL.md` + matching runbook in platform-ops |
| Author a policy | `tasks/policy-authoring/SKILL.md` |
| Understand platforms | `docs/platform-matrix.md` |

## Mentor Checklist

- [ ] Week 1 deliverable reviewed
- [ ] Nonprod cluster access verified
- [ ] Week 3 PR merged
- [ ] Week 4 tabletop completed
- [ ] Engineer added to PagerDuty schedule (after Week 4)
