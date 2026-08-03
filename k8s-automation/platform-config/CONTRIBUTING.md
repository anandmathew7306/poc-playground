# Contributing to platform-config

This repo is the GitOps source of truth for cluster configuration, RHACM policies, and client profiles. Every production change must go through a PR with validation passing locally before review.

## Prerequisites

Install these tools locally:

```bash
# macOS
brew install kustomize yq

# JSON Schema validation (pick one)
pip install check-jsonschema    # recommended
# or: npm install -g ajv-cli
```

## Validation steps

Run all applicable checks before opening a PR.

### 1. Validate client profiles against schema

Every field in `clients/[client]/profile.yaml` must be filled — no blanks.

```bash
check-jsonschema \
  --schemafile schemas/profile.schema.json \
  clients/acme/profile.yaml
```

For a new client, copy the template first:

```bash
cp -r clients/_template clients/[client]
# edit clients/[client]/profile.yaml
check-jsonschema \
  --schemafile schemas/profile.schema.json \
  clients/[client]/profile.yaml
```

### 2. Validate cluster metadata against schema

```bash
check-jsonschema \
  --schemafile schemas/cluster-info.schema.json \
  clusters/acme-prod/cluster-info.yaml
```

Validate all cluster-info files you touch:

```bash
for f in clusters/*/cluster-info.yaml; do
  [ -f "$f" ] && check-jsonschema --schemafile schemas/cluster-info.schema.json "$f"
done
```

### 3. Validate Kustomize builds

Ensure overlays resolve and render without errors:

```bash
# Platform bases
kustomize build base/rosa
kustomize build base/ocp
kustomize build base/ocp/namespaces
kustomize build base/ocp/rbac
kustomize build base/ocp/operators

# ACM resources
kustomize build acm/policies
kustomize build acm/placements
kustomize build acm/policy-sets

# Client overlays
kustomize build clients/acme/kustomize
kustomize build clients/acme/policies
```

Pipe to `kubectl apply --dry-run=client -f -` for an additional syntax check when connected to a cluster:

```bash
kustomize build clients/acme/kustomize | kubectl apply --dry-run=client -f -
```

### 4. Verify required platform.io labels

Namespaces and policies must include the standard label set. Spot-check rendered output:

```bash
kustomize build base/ocp/namespaces | grep platform.io
kustomize build acm/policies | grep platform.io
```

Required labels (see `platform-skills` core skill):

| Label | Values |
|-------|--------|
| `platform.io/client` | client slug |
| `platform.io/environment` | `prod`, `nonprod`, `dev` |
| `platform.io/platform` | `ocp`, `rosa`, `rosa-hcp`, `eks` |
| `platform.io/managed-by` | `kustomize` or `helm` |
| `platform.io/team` | `platrel` |

### 5. ACM policy checklist

When adding or changing policies under `acm/policies/`:

- [ ] Prefer vendoring from [policy-collection](https://github.com/stolostron/policy-collection) — see `acm/policies/README.md`
- [ ] Policy name is referenced in the client's `PolicySet` (`acm/policy-sets/`)
- [ ] `remediationAction` is `audit` first, then `enforce` after compliance is confirmed
- [ ] `namespaceSelector` excludes system namespaces (`openshift-*`, `kube-*`, `open-cluster-management*`)
- [ ] Two approvals required for policy changes (see PR process below)

### 6. Quick validation script

Run all checks in one pass:

```bash
set -e
echo "==> Schema: profile"
check-jsonschema --schemafile schemas/profile.schema.json clients/acme/profile.yaml
echo "==> Schema: cluster-info"
check-jsonschema --schemafile schemas/cluster-info.schema.json clusters/acme-prod/cluster-info.yaml
echo "==> Kustomize builds"
for dir in base/rosa base/ocp base/ocp/namespaces base/ocp/rbac \
           acm/policies acm/placements acm/policy-sets \
           clients/acme/kustomize clients/acme/policies; do
  echo "  building $dir"
  kustomize build "$dir" > /dev/null
done
echo "OK — all validations passed"
```

## Change types and requirements

| Change type | Requirements |
|-------------|--------------|
| Client profile | Complete all fields; validate against `schemas/profile.schema.json`; client anchor approval |
| Cluster metadata | Validate against `schemas/cluster-info.schema.json` |
| ACM policy | Two approvals; audit mode before enforce; ticket reference |
| Base/platform change | `kustomize build` all affected overlays; note blast radius in PR |
| Production change | Ticket reference in PR title or description |

## Pull request process

1. Branch from `main` using conventional commits (`feat:`, `fix:`, `chore:`, `docs:`)
2. Run validation steps above locally
3. Reference GitLab issue (`#<issue-number>`) and ticket ID in PR description
4. Get required approvals:
   - **Client profile changes** — client anchor approval
   - **ACM policy changes** — two approvals
   - **All production changes** — ticket reference required
5. Merge to `main`; Argo CD syncs automatically (no direct cluster edits)

## Onboarding a new client

1. Copy `clients/_template/` to `clients/[client]/`
2. Fill `profile.yaml` completely and validate against schema
3. Create `clusters/[cluster]/cluster-info.yaml` and `contacts.yaml`
4. Add `acm/placements/[client]-placement.yaml` and `acm/policy-sets/[client]-policy-set.yaml`
5. Wire overlays: `clients/[client]/kustomize/` → `base/[platform]`, `clients/[client]/policies/` → `acm/policies`
6. Create matching skill in `platform-skills/.cursor/skills/clients/[client]/SKILL.md`
7. Run `client: [name] | task: client-onboarding` after merge

## References

- Team standards: `platform-skills/.cursor/skills/core/SKILL.md`
- Client onboarding workflow: `platform-skills/.cursor/skills/tasks/client-onboarding/SKILL.md`
- Policy authoring: `platform-skills/.cursor/skills/tasks/policy-authoring/SKILL.md`
- Action plan: `docs/ACTION_PLAN.md` in the parent monorepo
