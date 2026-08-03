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
