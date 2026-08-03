# Incident Lifecycle

## Severity Definitions

| Severity | Definition | Response SLA |
|----------|------------|--------------|
| P1 | Production down or major functionality unavailable | 30 minutes |
| P2 | Degraded service, workaround available | 4 hours |
| P3 | Minor issue, no immediate client impact | Next business day |

## Lifecycle Stages

1. **Detection** — alert fires or client reports issue
2. **Triage** — engineer assesses severity, loads client profile and runbook
3. **Response** — follow runbook, use `client: [name] | task: incident-response`
4. **Resolution** — fix confirmed, monitoring green
5. **Follow-up** — runbook PR within 48h, postmortem for P1/P2, skill update if needed
6. **Close** — incident ticket closed with links to PRs

## Required Artifacts

Every closed incident must produce:
- Updated or new runbook in `platform-ops/runbooks/`
- Postmortem (P1/P2) in `platform-ops/postmortems/`
- Skill update (if agent lacked context) in `platform-skills/`

## Break-Glass

Emergency changes bypass normal process with `platform.io/break-glass: "INC-YYYY-NNN"` annotation. See `core` skill for full procedure.
