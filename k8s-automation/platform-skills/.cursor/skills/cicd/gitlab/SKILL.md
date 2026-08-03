---
name: cicd/gitlab
description: >
  Use when working with GitLab CI/CD pipelines for platform repos.
  Covers .gitlab-ci.yml, MR workflow, and PlatRel pipeline conventions.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: cicd
refs:
  - core
---

# CI/CD/GitLab

## When to Use
- Authoring or debugging `.gitlab-ci.yml` in platform repos
- MR pipeline failures for platform-skills, platform-config, platform-ops
- Setting up validation jobs (kustomize build, schema check, skill CI)
- Client application repos using GitLab with platform-skills submodule

## Key Concepts
- **Three repos**: each has its own GitLab project and pipeline
- **MR-only merges**: no direct pushes to `main`
- **Conventional commits**: `feat:`, `fix:`, `chore:`, `docs:` with `#issue` reference
- **Path-filtered jobs**: skill CI runs only when `.cursor/skills/**` changes
- **Protected branches**: `main` requires passing pipeline + approval

## Commands and Patterns

```bash
# Local pipeline validation (gitlab-ci-local if installed)
gitlab-ci-local --file .gitlab-ci.yml

# Kustomize validation (platform-config)
find clients -name kustomization.yaml -execdir kustomize build . \; > /dev/null

# Skill frontmatter validation (platform-skills)
find .cursor/skills -name SKILL.md -exec python3 scripts/validate-frontmatter.py {} \;

# Schema validation
python3 -c "import json, yaml, jsonschema; ..."  # or dedicated script

# MR workflow
git checkout -b feat/[short-description]
git push -u origin HEAD
# Open MR in GitLab UI; link #issue in description
```

## Pipeline Patterns by Repo

| Repo | Typical stages | Key jobs |
|------|----------------|----------|
| platform-skills | validate, security | frontmatter, Semgrep, allowlist |
| platform-config | validate, build | kustomize build, schema validate |
| platform-ops | validate | markdown lint, link check |

## Common Issues

**Pipeline fails: frontmatter validation**
- Missing required field: `name`, `description`, `status`, `layer`
- Run `python3 scripts/validate-frontmatter.py [file]` locally

**kustomize build fails in CI**
- Path references broken in overlay
- Fix locally: `cd clients/[client]/kustomize && kustomize build .`
- See: `deploy/kustomize`

**Semgrep blocks skill PR**
- Credential or prompt-injection pattern detected
- Review `.semgrep/skill-rules.yaml`; redact sensitive content

**MR stuck waiting for approval**
- Security-sensitive changes need two approvals per CONSTITUTION
- Client profile changes need client anchor approval

## References
- Skill CI spec: `.github/workflows/skill-ci.yaml` (or `.gitlab-ci.yml` equivalent)
- Contributing: `CONTRIBUTING.md`
- Workflow rule: conventional commits, issue references
