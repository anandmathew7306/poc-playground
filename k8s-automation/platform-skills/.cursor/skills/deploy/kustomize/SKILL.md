---
name: deploy/kustomize
description: >
  Use when deploying or modifying workloads via Kustomize base+overlay pattern.
  Covers kustomization.yaml structure, overlays, and GitOps validation.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: deploy
refs:
  - core
---

# Deploy/Kustomize

## When to Use
- Client profile specifies `deploy_tool: kustomize` or `deploy_skill: deploy/kustomize`
- Building or patching manifests in `platform-config/clients/[client]/kustomize/`
- Validating overlays before ACM placement or Argo CD sync
- Any GitOps change using `kustomization.yaml`

## Key Concepts
- **Base**: shared manifests in `platform-config/base/[platform]/`
- **Overlay**: client-specific customizations in `clients/[client]/kustomize/`
- **resources vs bases**: prefer `resources` (Kustomize v5+); `bases` deprecated but present in templates
- **patches**: strategic merge or JSON6902 for targeted changes
- **labels**: all resources must include `platform.io/*` labels per `core` skill

## Commands and Patterns

```bash
# Build overlay locally (always before PR)
cd platform-config/clients/[client]/kustomize
kustomize build . > /tmp/[client]-manifests.yaml

# Validate with kubeconform (if installed)
kustomize build . | kubeconform -kubernetes-version 1.28.0 -summary

# Diff against live cluster
kustomize build . | kubectl diff -f - 2>/dev/null || true

# Preview single resource
kustomize build . | yq 'select(.kind=="Deployment" and .metadata.name=="[name]")'

# Common overlay structure
# kustomization.yaml:
#   namespace: [client]-prod
#   resources:
#     - ../../../base/rosa
#   patches:
#     - path: replicas-patch.yaml
#   labels:
#     - pairs:
#         platform.io/client: [client]
#         platform.io/environment: prod
```

## Common Issues

**Build fails: resource not found**
- Check relative paths from overlay directory
- `kustomize build . --load-restrictor LoadRestrictionsNone` only for debugging — fix paths for production

**Duplicate resources / namespace mismatch**
- Ensure `namespace:` in kustomization.yaml matches client environment
- Remove duplicate resources across base and overlay

**Image tag not pinned**
- Production overlays must use SHA digest or semver — never `latest`
- Patch example:
```yaml
images:
  - name: registry.example.com/app
    newTag: sha256:abc123...
```

**ACM placement applies wrong overlay**
- Verify `clients/[client]/kustomize/kustomization.yaml` namespace matches Placement label selector
- See: `acm/placement`

## References
- Config: `platform-config/clients/_template/kustomize/`
- Bases: `platform-config/base/`
- Standards: `core` (labels, security gates)
- Example: `platform-config/clients/acme/kustomize/`
