# platform-skills

AI skill library for the **PlatRel** (Platform Reliability) team. This repository teaches Cursor agents how the team works — platform standards, troubleshooting patterns, task workflows, and client-specific overlays.

Skills live under `.cursor/skills/` and compose via frontmatter `refs`. When you prompt Cursor with `client: acme | task: incident-response`, the agent loads the client overlay, resolves the skill chain from `platform-config/clients/acme/profile.yaml`, and applies operational knowledge without duplicating content across skills.

## Structure

| Path | Purpose |
|------|---------|
| `.cursor/skills/core/` | Team-wide standards — always active |
| `.cursor/skills/platform/` | OCP, ROSA, ROSA HCP, EKS operations |
| `.cursor/skills/cloud/` | AWS (active), Azure (stub) |
| `.cursor/skills/deploy/` | Kustomize GitOps patterns |
| `.cursor/skills/acm/` | RHACM policies and placement |
| `.cursor/skills/observability/` | Prometheus, health checks, OTel/logging stubs |
| `.cursor/skills/troubleshooting/` | Diagnostic playbooks by domain |
| `.cursor/skills/tasks/` | End-to-end workflows (onboarding, incidents, health checks) |
| `.cursor/skills/clients/` | Per-client overlays (e.g. Acme) |
| `docs/` | Platform matrix, onboarding bootcamp |
| `governance/` | Skill review checklist, allowlist |

## How to Use with Cursor

1. Clone this repo (or add as submodule to your app repo — see `example-app-repo/`)
2. Ensure `.cursor/skills/` is visible to Cursor (project root or symlink)
3. Start prompts with: `client: [name] | task: [task-skill] | [context]`
4. The agent loads `core` + client profile skills + task skill `refs` chain
5. For incidents, it cross-references `platform-ops/runbooks/` automatically

Read `CONSTITUTION.md` before contributing. Pair with **platform-config** (IaC) and **platform-ops** (runbooks) for the full three-repo model.
