# Skill Review Checklist

Use this checklist for every PR that adds or modifies a skill under `.cursor/skills/`. External skills (imported from outside PlatRel) require all items plus two human approvals.

## Author Self-Review (before opening PR)

### Structure and Frontmatter

- [ ] File is named `SKILL.md` in the correct layer directory
- [ ] YAML frontmatter present with required fields: `name`, `description`, `status`, `layer`
- [ ] `description` states clear trigger conditions ("Use when…")
- [ ] `status` is correct: `active`, `stub`, or `deprecated`
- [ ] `version` bumped appropriately (patch for fixes, minor for new sections, major for breaking changes)
- [ ] `reviewed_at` set to today's date (ISO `YYYY-MM-DD`)
- [ ] `refs` lists composed skills — no duplicated platform content in task skills

### Content Quality

- [ ] All `[placeholder]` sections replaced with operational content
- [ ] Commands are copy-paste ready (`oc`, `kubectl`, `aws` as appropriate)
- [ ] Common Issues section covers at least two real scenarios
- [ ] References point to platform-ops runbooks, platform-config paths, or other skills
- [ ] Concise — no essay-length prose; tables and bullet lists preferred
- [ ] Stub skills include prominent "not yet active" notice if `status: stub`

### Security (Law 2 + Skill Security Compact)

- [ ] No hardcoded credentials, tokens, SSH keys, or webhook URLs
- [ ] No `curl | bash` patterns
- [ ] No prompt injection phrases ("ignore previous instructions", etc.)
- [ ] No external skill URLs without SHA pin in `governance/allowed-skills.sha256`
- [ ] Scripts bundled with skill (`.sh`, `.py`) scanned by Snyk in CI

### Composition Rules (CONSTITUTION Law 2)

- [ ] Task skills reference platform/cloud/acm skills — they do not duplicate commands
- [ ] Platform-specific steps live in `platform/*` or `cloud/*` skills only
- [ ] Client-specific overrides live in `clients/[client]/SKILL.md`, not in generic skills

## Reviewer Checklist

### First Reviewer

- [ ] CI green: frontmatter validation, Semgrep scan
- [ ] Commands verified against current platform version (OCP 4.14+, EKS 1.28+)
- [ ] `refs` chain is complete — task skill loads correct dependencies
- [ ] No conflict with `core/SKILL.md` naming or security gates
- [ ] Runbook cross-links exist in platform-ops (or runbook PR linked)

### Second Reviewer (required for)

- External/imported skills
- Skills with `allowed-tools: bash` or network access
- Security policy changes
- `status` change from `stub` to `active`

- [ ] Independent verification of security items above
- [ ] Spot-check: run at least one command from the skill on nonprod
- [ ] Approve or request changes with specific line references

## External Skill Additional Requirements

- [ ] SHA-256 hash added to `governance/allowed-skills.sha256`
- [ ] Source URL and pin tag documented in PR description
- [ ] Two PlatRel engineer approvals recorded
- [ ] Semgrep and Snyk CI jobs passed
- [ ] No broader tool permissions than the task requires

## Post-Merge

- [ ] If new platform or cloud: update `docs/platform-matrix.md`
- [ ] If client-affecting: verify `profile.yaml` `active_skills` list includes new skill
- [ ] Announce in team channel if skill changes incident response workflow

## Review Cadence

| Check | Frequency | Owner |
|-------|-----------|-------|
| `reviewed_at` > 90 days | Bi-weekly | Skill layer owner |
| Stub → active promotion | When platform goes live | Platform lead |
| allowed-skills.sha256 audit | Monthly | Security champion |

## Quick Reject Reasons

| Finding | Action |
|---------|--------|
| Platform commands in task skill | Move to platform skill; add ref |
| Missing `refs` on task skill | Request author fix |
| Semgrep credential rule hit | Block merge; redact content |
| `reviewed_at` empty on active skill | Request author set date |
| Duplicate of existing skill | Merge or deprecate old skill |
