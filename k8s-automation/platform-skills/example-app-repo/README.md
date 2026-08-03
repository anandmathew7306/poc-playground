# Example Application Repo

Reference example showing how a client application repository consumes `platform-skills` for AI-assisted development.

## How Skills Are Consumed

This repo uses `platform-skills` as a **git submodule** pinned to a specific release tag. Skills are available at `.cursor/skills/` and are loaded automatically by Cursor when you work in this repository.

## First-Time Setup

After cloning this repo, run:

```bash
./scripts/init-skills.sh v1.0.0
```

Or, if the submodule is already configured:

```bash
git submodule update --init
```

## Working on a Client Task

Use the short prompt format defined in the `core` skill:

```
client: acme | task: client-onboarding
client: acme | task: platform-health-check
client: acme | task: incident-response | alert: HostedClusterDegraded
```

## Updating Skills to a New Version

When a new `platform-skills` release is approved:

```bash
cd .cursor/skills && git checkout tags/vX.Y.Z && cd ../..
git add .cursor/skills
git commit -m "chore: pin platform-skills to vX.Y.Z"
```

## Directory Layout

```
example-app-repo/
  README.md             ← this file
  .gitmodules           ← submodule pointing to platform-skills
  .cursor/
    skills/             ← submodule target (platform-skills repo)
  scripts/
    init-skills.sh      ← one-time setup script
```

## Related Repos

| Repo | Purpose |
|------|---------|
| platform-skills | AI skill library |
| platform-config | IaC, client profiles, SLOs |
| platform-ops | Runbooks, postmortems, SOPs |
