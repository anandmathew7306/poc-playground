# Contributing to platform-skills

## Overview

This repo contains Cursor agent skills for the PlatRel platform team. Every change must go through a merge request. Skills encode operational knowledge — treat them like runbooks for agents.

## Before You Contribute

1. Read `CONSTITUTION.md` (especially Law 2: task skills compose, never duplicate)
2. Review `governance/skill-review-checklist.md`
3. Check `docs/platform-matrix.md` for platform/cloud scope
4. Copy frontmatter format from an existing active skill (e.g. `core/SKILL.md`)

## Authoring a New or Updated Skill

### 1. Branch and edit

```bash
git checkout main
git pull
git checkout -b feat/[skill-name]-[short-description]
```

Edit `SKILL.md` in the correct layer directory. Required sections:
- When to Use
- Key Concepts
- Commands and Patterns
- Common Issues
- References

### 2. Frontmatter requirements

```yaml
---
name: [skill-name]
description: >
  Use when [trigger]. Covers [topics].
status: active          # or stub | deprecated
reviewed_at: "YYYY-MM-DD"
version: 1.0.0          # semver; 0.1.0 for stubs
layer: [layer]
refs:
  - core
  - [other-composed-skills]
---
```

### 3. Validate locally

```bash
# Frontmatter check
python3 scripts/validate-frontmatter.py .cursor/skills/[path]/SKILL.md

# Confirm no placeholders remain
grep -r "\[placeholder\]" .cursor/skills/[path]/
```

### 4. Open merge request

```bash
git add .cursor/skills/[path]/SKILL.md
git commit -m "feat: fill [skill-name] with operational content #ISSUE"
git push -u origin HEAD
```

MR title: `feat: [what changed]` (conventional commit style)

MR description template:

```markdown
## Summary
- [what the skill now covers]

## Skill details
- Layer: [layer]
- Status: [active/stub]
- Composes: [refs list]

## Checklist
- [ ] governance/skill-review-checklist.md author items complete
- [ ] No [placeholder] sections remain
- [ ] reviewed_at updated
- [ ] CI passes (frontmatter + Semgrep)

## Test plan
- [ ] Ran at least one command from the skill on nonprod
- [ ] Task skill refs chain verified (if applicable)

Closes #ISSUE
```

### 5. Review and merge

| Change type | Approvals required |
|-------------|-------------------|
| Docs-only fix | 1 |
| Active skill content | 1 |
| External/imported skill | 2 + allowlist SHA |
| Security policy / break-glass | 2 |
| stub → active promotion | 2 + platform lead |

CI must pass before merge. Reviewers use `governance/skill-review-checklist.md`.

### 6. Post-merge

- Update `docs/platform-matrix.md` if new platform/cloud added
- Update client `profile.yaml` `active_skills` if client-affecting
- Announce in team channel if incident workflow changes

## Rules (non-negotiable)

- Task skills **reference** platform/cloud/acm skills — never copy their commands
- No credentials, `curl | bash`, or prompt injection in skill content
- External skills require SHA pin in `governance/allowed-skills.sha256`
- `reviewed_at` must not exceed 90 days — refresh skills bi-weekly

## Getting Help

- New engineer onboarding: `docs/onboarding-bootcamp.md`
- Example client pattern: `.cursor/skills/clients/acme/SKILL.md`
- Action plan: parent repo `docs/ACTION_PLAN.md`
