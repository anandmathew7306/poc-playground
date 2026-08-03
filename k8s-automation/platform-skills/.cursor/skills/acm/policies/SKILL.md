---
name: acm/policies
description: >
  Use when authoring, applying, or troubleshooting RHACM governance policies.
  Covers Policy, PolicySet, PolicyGenerator (RHACM 2.16), templating boilerplate,
  PlacementBinding, and compliance. Target: no hardcoded cluster values.
status: active
reviewed_at: "2026-06-13"
version: 1.2.0
layer: acm
refs:
  - core
  - acm/placement
  - deploy/kustomize
---

# ACM/Policies

## When to Use
- Creating or updating Kyverno, Gatekeeper, or ACM ConfigurationPolicy rules
- Generating policies from plain Kubernetes manifests via **PolicyGenerator**
- Policy non-compliance alerts on managed clusters
- Binding policies to clients via PolicySet + Placement
- Client profile has `acm.managed: true`

## RHACM Version Reference

| Item | Value |
|------|-------|
| **Latest GA** | RHACM **2.16** (GA March 2026, [release notes](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.16/html-single/release_notes/index)) |
| **Bundled MCE** | Multicluster engine **2.11** (cluster lifecycle) |
| **Governance docs** | [RHACM 2.16 Governance](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.16/html/governance/governance) |
| **Supported OCP** | Current OCP + two previous minor versions + next upcoming (see [2.16 support matrix](https://access.redhat.com/articles/7136928)) |
| **Deprecated** | PlacementRule (use Placement API); RHACM ≤2.9 unsupported |
| **PlatRel target** | RHACM 2.14+ minimum; author for **2.16** APIs and template functions |

PolicyGenerator, Placement API, `object-templates-raw`, and `policytools template-resolver` are stable in 2.14–2.16. Always verify template output on nonprod before enforce on prod.

---

## Key Concepts

| Concept | Role |
|---------|------|
| **Hub cluster** | Runs ACM controllers; policies defined and propagated from here |
| **Policy** | Top-level governance object with one or more `policy-templates` |
| **ConfigurationPolicy** | Template that compares/enforces `object-templates` on managed clusters |
| **PolicyGenerator** | Kustomize plugin that wraps K8s YAML into Policy + Placement + PlacementBinding |
| **PolicySet** | Groups policies for a client; single PlacementBinding for the set |
| **Placement** | Selects managed clusters (prefer over deprecated PlacementRule) |
| **Compliance** | `Compliant`, `NonCompliant`, `Pending` per policy per cluster |

### Hand-written Policy vs PolicyGenerator

| Approach | Use when |
|----------|----------|
| **Hand-written Policy CR** | Single ConfigurationPolicy, vendored from [policy-collection](https://github.com/stolostron/policy-collection), or fine-grained control |
| **PolicyGenerator** | You have standard K8s manifests (ConfigMap, Subscription, Namespace, Kyverno/Gatekeeper CRs) and want GitOps-friendly generation |

PolicyGenerator is a **Kustomize exec plugin** ([policy-generator-plugin](https://github.com/open-cluster-management-io/policy-generator-plugin)). It builds `Policy`, `Placement`, `PlacementBinding`, and optionally `PolicySet` from a `PolicyGenerator` CR plus manifest files.

---

## PolicyGenerator Structure

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: PolicyGenerator
metadata:
  name: <generator-name>          # unique per file

placementBindingDefaults:
  name: <binding-name>            # consolidate bindings — one per generator

policyDefaults:
  namespace: open-cluster-management
  remediationAction: inform       # inform | enforce — override per policy
  severity: medium
  standards: [NIST SP 800-53]
  categories: [CM Configuration Management]
  controls: [CM-2 Baseline Configuration]
  consolidateManifests: true      # one ConfigurationPolicy per policy entry (default)
  informKyvernoPolicies: true     # auto-generate inform policy for Kyverno CRs
  informGatekeeperPolicies: true  # auto-generate inform policy for Gatekeeper CRs
  evaluationInterval:
    compliant: 30m
    noncompliant: watch
  placement:
    placementPath: ../placements/acme-placement.yaml   # reuse existing Placement
    # OR generate Placement from selectors:
    # labelSelector:
    #   matchLabels:
    #     platform.io/client: acme
    # name: acme-placement        # consolidate Placements with same selectors
    # OR reference live Placement:
    # placementName: acme-placement
  policySets:
    - acme-policy-set             # join generated policies to a PolicySet

policies:
  - name: require-platform-labels
    remediationAction: enforce
    manifests:
      - path: manifests/require-labels.yaml
        patches:                    # Kustomize strategic merge per manifest
          - apiVersion: v1
            kind: Namespace
            metadata:
              labels:
                platform.io/team: platrel

policySets:
  - name: acme-policy-set
    description: Baseline policies for Acme
    placement:
      placementPath: ../placements/acme-placement.yaml
```

### Top-level sections

| Section | Required | Purpose |
|---------|----------|---------|
| `metadata.name` | Yes | Identifies the generator config file |
| `policyDefaults` | Yes | Shared namespace, remediation, placement, annotations |
| `placementBindingDefaults` | Recommended | Single PlacementBinding name — avoids one binding per policy |
| `policies[]` | Yes | List of policies to generate; each has `name` + `manifests[]` |
| `policySets[]` | Optional | Generate PolicySet CRs; link via `policyDefaults.policySets` or `policies[].policySets` |

### Manifest path behaviour

Paths in `manifests[].path` are **relative to the `kustomization.yaml`** that references the generator. Three manifest types:

1. **Plain K8s resources** (ConfigMap, Namespace, Subscription, etc.) — wrapped in auto-generated `ConfigurationPolicy`
2. **Policy-suffixed CRs** (`*Policy` kinds like `CertificatePolicy`) — added directly to `policy-templates` unchanged
3. **`object-templates-raw` only** — used verbatim inside a generated `ConfigurationPolicy` (see Templating below)

Subdirectories with their own `kustomization.yaml` are built as Kustomize overlays. Paths **cannot** point outside the kustomization root.

---

## PolicyGenerator Examples

### Example 1 — ConfigMap distribution (audit → enforce)

**kustomization.yaml**
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
generators:
  - policy-generator.yaml
```

**manifests/cluster-monitoring-config.yaml** (plain K8s manifest)
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-monitoring-config
  namespace: openshift-monitoring
data:
  config.yaml: |
    enableUserWorkload: true
```

**policy-generator.yaml**
```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: PolicyGenerator
metadata:
  name: acme-monitoring
placementBindingDefaults:
  name: binding-acme-monitoring
policyDefaults:
  namespace: open-cluster-management
  remediationAction: inform
  placement:
    placementPath: ../placements/acme-placement.yaml
  policySets:
    - acme-policy-set
policies:
  - name: policy-user-workload-monitoring
    remediationAction: enforce
    manifests:
      - path: manifests/cluster-monitoring-config.yaml
```

### Example 2 — Reuse Placement + PolicySet (PlatRel pattern)

Matches `platform-config/acm/` layout:

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: PolicyGenerator
metadata:
  name: acme-baseline
placementBindingDefaults:
  name: binding-acme-baseline
policyDefaults:
  namespace: open-cluster-management
  remediationAction: enforce
  severity: medium
  standards: [NIST SP 800-53]
  controls: [CM-2 Baseline Configuration]
  placement:
    placementName: acme-placement    # Placement already in hub — see acm/placements/
  policySets:
    - acme-policy-set
policies:
  - name: require-platform-labels
    manifests:
      - path: manifests/namespace-label-requirements.yaml
```

Hand-written equivalent already in repo: `platform-config/acm/policies/require-platform-labels.yaml`.

### Example 3 — Kyverno policy (auto inform-policy)

Place Kyverno `ClusterPolicy` YAML in `manifests/`. Generator wraps it and, when `informKyvernoPolicies: true` (default), adds an `inform-*` ConfigurationPolicy that surfaces violations in ACM UI.

```yaml
policies:
  - name: policy-kyverno-require-labels
    remediationAction: inform
    manifests:
      - path: manifests/kyverno/require-labels.yaml
```

Set `informKyvernoPolicies: false` in `policyDefaults` to deploy Kyverno CR only without the companion inform policy.

### Example 4 — Policy ordering and dependencies

```yaml
policyDefaults:
  orderPolicies: true    # apply policies[] in list order via Policy dependencies
policies:
  - name: policy-namespaces-first
    manifests:
      - path: manifests/namespaces.yaml
  - name: policy-operators-second
    dependencies:
      - name: policy-namespaces-first
        compliance: Compliant
    manifests:
      - path: manifests/subscriptions/
```

Use `orderManifests: true` (with `consolidateManifests: false`) to order manifests within a single policy.

---

## Build and GitOps Workflow

```bash
# Install plugin (once per CI runner / laptop)
# https://github.com/open-cluster-management-io/policy-generator-plugin

# Generate policies locally
kustomize build --enable-alpha-plugins path/to/policy/dir

# Or standalone binary
PolicyGenerator policy-generator.yaml

# Debug failed generation
PolicyGenerator --debug policy-generator.yaml

# Helm charts in manifests (optional)
POLICY_GEN_ENABLE_HELM=true kustomize build --enable-alpha-plugins .
```

**Two-stage GitOps (recommended):**
1. **Stage 1** — maintain plain manifests in `manifests/` (base + overlays per env/client)
2. **Stage 2** — PolicyGenerator + `kustomize build` produces final `Policy`/`Placement` YAML committed or applied by OpenShift GitOps

Environment variables:
- `POLICY_GEN_ENABLE_HELM=true` — process Helm charts in manifest paths
- `POLICY_GEN_DISABLE_LOAD_RESTRICTORS=true` — allow paths outside kustomization root (use sparingly)

Pair with `deploy/kustomize` skill for overlay patterns. Hub GitOps Application should target `platform-config/acm/` or `clients/[client]/policies/`.

---

## How Templating Works (RHACM 2.16)

ConfigurationPolicy and OperatorPolicy support **Golang text templates** (Sprig functions included). Templates produce valid YAML after resolution — invalid output causes policy violations on all target clusters.

### Resolution pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ HUB CLUSTER                                                     │
│  1. Policy + ConfigurationPolicy created/updated                │
│  2. Hub templates {{hub ... hub}} resolved per ManagedCluster   │
│     (runs once at create/update — NOT on every reconcile)       │
│  3. Replicated policy written to managed-cluster namespace      │
└────────────────────────────┬────────────────────────────────────┘
                             │ propagate
┌────────────────────────────▼────────────────────────────────────┐
│ MANAGED CLUSTER                                                 │
│  4. Managed templates {{ ... }} resolved periodically             │
│  5. Fully resolved object-templates compared / enforced           │
└─────────────────────────────────────────────────────────────────┘
```

| Stage | Delimiter | When processed | Re-evaluates when |
|-------|-----------|----------------|-------------------|
| **Hub** | `{{hub ... hub}}` | Propagation to each cluster | Policy/template created or updated |
| **Managed** | `{{ ... }}` | On managed cluster | Periodic (ConfigurationPolicy) or on resource change (OperatorPolicy) |

**Exactly one** of `object-templates` or `object-templates-raw` per ConfigurationPolicy.

### Context variables (hub templates)

Available inside `{{hub ... hub}}` without API calls:

| Variable | Resolves to |
|----------|-------------|
| `ManagedCluster` | Full ManagedCluster object for propagation target |
| `.ManagedClusterName` | Target cluster name |
| `.ManagedClusterLabels` | Map of labels on target ManagedCluster |
| `.PolicyMetadata` | Root policy `name`, `namespace`, `labels`, `annotations` |

**PlatRel convention:** drive all client/env values from `ManagedCluster` labels set at import time:

```yaml
# Expected ManagedCluster labels (set by cluster onboarding)
metadata:
  labels:
    platform.io/client: acme
    platform.io/environment: prod
    platform.io/platform: rosa-hcp
    cloud: Amazon
    region: eu-west-1
```

### Template functions (common)

| Function | Scope | Purpose |
|----------|-------|---------|
| `fromConfigMap` | Hub or managed | Read ConfigMap data key |
| `fromSecret` | Hub or managed | Read Secret data key (auto-encrypted in hub templates) |
| `fromClusterClaim` | Hub | Read ManagedClusterClaim value |
| `lookup` | Hub or managed | Generic resource fetch as JSON map |
| `copySecretData` / `copyConfigMapData` | Hub | Copy entire data map (secrets auto-encrypted) |
| `protect` | Hub | Encrypt sensitive non-secret values in flight |
| `getNodesWithExactRoles` / `hasNodesWithExactRoles` | Managed | OpenShift node role checks |
| `skipObject` | Managed | Conditionally skip an object-template entry |
| Sprig (`default`, `printf`, `eq`, `range`, etc.) | Both | String/logic utilities |

Hub lookups are **restricted to the policy namespace** unless `hubTemplateOptions.serviceAccountName` is set on the ConfigurationPolicy (SA needs `list`/`watch` on referenced resources).

### object-templates vs object-templates-raw

| Field | Use when |
|-------|----------|
| `object-templates` | Static structure; inline `{{ }}` / `{{hub hub}}` in field values |
| `object-templates-raw` | Dynamic list of templates: `range` over clusters/nodes/ConfigMaps, `if/else` branches, multi-object generation |

Raw template must render a **YAML array** of `object-templates` entries.

### Debug templates before enforce

```bash
# RHACM 2.14+ — resolve templates locally without applying
policytools template-resolver \
  --cluster-name acme-prod \
  --hub-kubeconfig ~/.kube/hub-config \
  --policy manifests/templated-policy.yaml

# Save hub/managed resources for dryrun
policytools template-resolver \
  --cluster-name acme-prod \
  --hub-kubeconfig ~/.kube/hub-config \
  --save-resources /tmp/managed-state/ \
  --save-hub-resources /tmp/hub-state/ \
  --policy manifests/templated-policy.yaml

# Force hub template reprocess after ManagedCluster label change
oc annotate policy <name> -n open-cluster-management \
  policy.open-cluster-management.io/reprocess-sync-versions=""
```

Standalone GitOps (policies on managed cluster only): install `governance-standalone-hub-templating` add-on; use `.ManagedClusterLabels` in hub templates on the spoke.

---

## How Templating Should Work (Design Rules)

When an AI or engineer authors policies, follow these rules so **one policy serves all clusters** with zero hardcoded client/cluster values.

### Rule 1 — No hardcoded cluster identity

| Forbidden | Replace with |
|-----------|--------------|
| `name: acme-prod` | `{{hub .ManagedClusterName hub}}` or label-driven naming |
| `platform.io/client: acme` literal | `{{hub index .ManagedClusterLabels "platform.io/client" hub}}` |
| `region: eu-west-1` | `{{hub index .ManagedClusterLabels "region" hub}}` |
| Fixed namespace per client | `{{hub printf "%s-monitoring" (index .ManagedClusterLabels "platform.io/client") hub}}` |

### Rule 2 — Choose the right template stage

| Data source | Stage | Example |
|-------------|-------|---------|
| ManagedCluster labels/claims | Hub | Client, env, region, platform |
| Hub-side per-cluster ConfigMap | Hub + `fromConfigMap` | Cluster config registry on hub |
| Live cluster state (nodes, infra, MachineSet) | Managed | Replica counts, infrastructure ID |
| Secrets | Hub `fromSecret` / `copySecretData` | Never plaintext in policy YAML |

### Rule 3 — Sensitive data never in Git

- Do not commit secrets, tokens, or credentials in policy manifests
- Hub: `fromSecret` / `copySecretData` (auto-encrypted via `protect`)
- Managed: reference existing Secrets with `fromSecret` — do not embed values
- `recordDiff: None` on Secret/ConfigMap kinds (default in RHACM 2.16)

### Rule 4 — Inform first, enforce after validation

1. Ship with `remediationAction: inform`
2. Run `policytools template-resolver` for each target cluster profile
3. Verify compliance on nonprod Placement
4. Promote to `enforce` via PR — never skip validation

### Rule 5 — Load client context from profile.yaml

Before authoring, read `platform-config/clients/[client]/profile.yaml`:
- `spec.platform`, `spec.cloud` → expected ManagedCluster labels
- `spec.acm.policy_set`, `spec.acm.placement` → PolicyGenerator placement refs
- `spec.terminology.environment_names` → template conditionals for env naming
- `spec.compliance.frameworks` → policy annotations (NIST, SOC2 controls)

### Rule 6 — One policy, many clusters

If you need separate policy files per cluster, you have failed templating. Refactor to hub labels or managed `lookup` instead.

---

## AI Policy Authoring Boilerplate

Use this **repeatable directory structure** for every new policy. Copy per client; parameterise only via templates and ManagedCluster labels.

```
platform-config/acm/policies/
  kustomization.yaml
  policy-generator.yaml
  namespaces.yaml                    # Namespace CRs — NEVER inside PolicyGenerator file
  manifests/
    <policy-name>/
      object-templates-raw.yaml      # OR static manifest / ConfigurationPolicy fragment
      README.md                      # what it enforces, which labels required
  hub-config/                        # optional per-cluster data (NOT secrets)
    <cluster>/configmap.yaml         # referenced via fromConfigMap in templates
```

### Boilerplate: kustomization.yaml

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - namespaces.yaml
generators:
  - policy-generator.yaml
```

### Boilerplate: policy-generator.yaml

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: PolicyGenerator
metadata:
  name: platrel-baseline
placementBindingDefaults:
  name: binding-platrel-baseline
policyDefaults:
  namespace: open-cluster-management
  remediationAction: inform          # promote to enforce after validation
  severity: medium
  standards: [NIST SP 800-53]
  controls: [CM-2 Baseline Configuration]
  consolidateManifests: true
  hubTemplateOptions:
    serviceAccountName: policy-generator-hub-reader   # if cross-resource hub lookups needed
  placement:
    placementPath: ../placements/acme-placement.yaml  # or labelSelector — never hardcode cluster names
  policySets:
    - acme-policy-set
policies:
  - name: policy-platform-labels
    remediationAction: inform
    manifests:
      - path: manifests/platform-labels/object-templates-raw.yaml
```

### Boilerplate: object-templates-raw.yaml (no hardcoded values)

```yaml
# PolicyGenerator manifest type 3 — only object-templates-raw key
object-templates-raw: |
  {{- /* All cluster-specific values from ManagedCluster labels — set at import */ -}}
  - complianceType: musthave
    objectDefinition:
      apiVersion: v1
      kind: Namespace
      metadata:
        name: '{{hub printf "%s-platform" (index .ManagedClusterLabels "platform.io/client") hub}}'
        labels:
          platform.io/client: '{{hub index .ManagedClusterLabels "platform.io/client" hub}}'
          platform.io/environment: '{{hub index .ManagedClusterLabels "platform.io/environment" hub}}'
          platform.io/platform: '{{hub index .ManagedClusterLabels "platform.io/platform" hub}}'
          platform.io/managed-by: kustomize
          platform.io/team: platrel
  - complianceType: musthave
    objectDefinition:
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: cluster-metadata
        namespace: '{{hub printf "%s-platform" (index .ManagedClusterLabels "platform.io/client") hub}}'
      data:
        clusterName: '{{hub .ManagedClusterName hub}}'
        region: '{{hub index .ManagedClusterLabels "region" hub | default "unknown" hub}}'
        # Managed-cluster template — resolved on spoke after propagation
        infrastructureID: '{{ (lookup "config.openshift.io/v1" "Infrastructure" "" "cluster").status.infrastructureName }}'
```

### Boilerplate: static manifest with inline templates (simpler policies)

```yaml
apiVersion: policy.open-cluster-management.io/v1
kind: ConfigurationPolicy
metadata:
  name: demo-templated-configmap
spec:
  remediationAction: inform
  severity: medium
  hubTemplateOptions:
    serviceAccountName: policy-generator-hub-reader
  object-templates:
    - complianceType: musthave
      objectDefinition:
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: platrel-cluster-info
          namespace: openshift-config
        data:
          client: '{{hub index .ManagedClusterLabels "platform.io/client" hub}}'
          environment: '{{hub index .ManagedClusterLabels "platform.io/environment" hub}}'
          managedCluster: '{{hub .ManagedClusterName hub}}'
```

### AI authoring checklist (run before every PR)

```
[ ] Loaded clients/[client]/profile.yaml — platform, placement, policy_set confirmed
[ ] Zero hardcoded cluster names, client slugs, regions, or env values
[ ] All cluster-specific values use .ManagedClusterLabels or .ManagedClusterName
[ ] Managed-cluster lookups only for live state (nodes, infra, MachineSets)
[ ] No secrets in Git — fromSecret/copySecretData if needed
[ ] remediationAction: inform on first merge
[ ] policytools template-resolver run for ≥1 nonprod + 1 prod-shaped cluster
[ ] Placement matches platform.io/client label on ManagedCluster
[ ] Namespace CRs in namespaces.yaml, not in PolicyGenerator CR
[ ] Ticket reference in PR (core skill security gate)
```

### Anti-patterns (reject in review)

| Anti-pattern | Why it fails |
|--------------|--------------|
| `clients/acme/policy.yaml` + `clients/globex/policy.yaml` duplicate | Use one templated policy + labels |
| `region: eu-west-1` in objectDefinition | Breaks multi-region clients |
| Secret `data:` in policy manifest | Credential leak; fails Semgrep/core gate |
| Hub `lookup` without `serviceAccountName` | Cross-namespace lookup fails silently |
| Skip `template-resolver` before enforce | Production outage from bad YAML render |

---

## Best Practices

### Policy count and performance
- **Minimize policy count** — each policy adds hub + managed-cluster CPU load
- Group related manifests under one `policies[].name` (`consolidateManifests: true`, default)
- Split only when remediation, placement, or evaluation intervals differ

### Placement
- Prefer **Placement** API over deprecated **PlacementRule** (OCP 4.16+ / RHACM 2.11+)
- Reuse `placementPath` or `placementName` — do not generate duplicate Placements per policy
- Use `placementBindingDefaults.name` + `placement.name` to consolidate bindings and placements
- Ensure `ManagedClusterSetBinding` exists for the policy namespace on the target ClusterSet (often `global`)
- PlatRel labels: `platform.io/client`, `platform.io/environment` — see `acm/placement` skill

### PolicySet integration
- When policies join a PolicySet, per-policy PlacementBindings are **not** generated (set handles binding)
- Set `generatePlacementWhenInSet: true` only if a policy needs its own placement *in addition* to the set
- Reference client PolicySet from `profile.yaml` → `spec.acm.policy_set`

### Manifest hygiene
- Keep **Namespace CRs in a separate file** — not in the same file as PolicyGenerator
- Pin Subscription `channel`/`source` versions explicitly — prevents surprise upgrades when source CRs change
- Use `policyDefaults.remediationAction: inform` globally; override to `enforce` per policy after validation
- Vendor from [policy-collection](https://github.com/stolostron/policy-collection) before authoring from scratch

### Security gates (from core skill)
- Audit (`inform`) on nonprod clusters first; enforce on prod only after compliance verified
- Never put secrets in policies — use hub templates referencing existing Secrets or External Secrets
- `recordDiff` defaults to `None` for Secret/ConfigMap kinds — avoid logging sensitive diffs

### GitOps layout (PlatRel convention)

```
platform-config/acm/
  placements/acme-placement.yaml
  policy-sets/acme-policy-set.yaml
  policies/
    kustomization.yaml          # generators: [policy-generator.yaml] OR static Policy CRs
    policy-generator.yaml
    manifests/
      require-labels.yaml
clients/acme/policies/
  kustomization.yaml            # overlay → ../../../acm/policies
```

---

## Commands and Patterns

```bash
# Hub cluster context required
oc config use-context hub-prod

# --- PolicyGenerator ---
kustomize build --enable-alpha-plugins platform-config/acm/policies/

# --- Policies and compliance ---
oc get policies -n open-cluster-management
oc get policies -n open-cluster-management \
  -o custom-columns=NAME:.metadata.name,COMPLIANT:.status.compliant

oc describe policy require-platform-labels -n open-cluster-management
oc get policy require-platform-labels -n open-cluster-management -o yaml | grep -A30 status

# --- PolicySet ---
oc get policyset acme-policy-set -n open-cluster-management -o yaml

# --- Placement / binding ---
oc get placement acme-placement -n open-cluster-management
oc get placementdecision -n open-cluster-management | grep acme
oc get placementbinding -n open-cluster-management | grep acme

# --- On managed cluster ---
oc get policyreport -A
oc get configurationpolicies.policy.open-cluster-management.io -A 2>/dev/null

# --- Template debugging (RHACM 2.14+) ---
policytools template-resolver \
  --cluster-name acme-prod \
  --hub-kubeconfig ~/.kube/hub-config \
  --policy /path/to/policy.yaml

oc get configurationpolicy -n open-cluster-management -o yaml | grep -A5 object-templates

# Reprocess hub templates after ManagedCluster label change
oc annotate policy <name> -n open-cluster-management \
  policy.open-cluster-management.io/reprocess-sync-versions=""

# --- Remediation ---
# Switch policy to inform (audit only)
oc patch policy require-platform-labels -n open-cluster-management \
  --type=merge -p '{"spec":{"remediationAction":"inform"}}'
```

---

## Common Issues

**PolicyGenerator build fails**
- Run `PolicyGenerator --debug policy-generator.yaml`
- Check manifest paths are relative to kustomization.yaml and inside repo root
- Patch requires `apiVersion`, `kind`, `metadata.name` when multiple manifests share a path

**Generated policy not on expected clusters**
- Verify `placementPath` / `placementName` / `labelSelector` matches `ManagedCluster` labels
- Check `PlacementDecision` includes target cluster: `oc get placementdecision -n open-cluster-management -o yaml`
- See: `acm/placement`

**Policy NonCompliant**
- `oc describe policy [name]` — read `status.compliantClusters` and violation messages
- Distinguish audit vs enforce; check if template rendered empty values
- See: `troubleshooting/acm-policies`, `platform-ops/runbooks/acm/policy-noncompliant.md`

**Template renders wrong on managed cluster**
- Inspect hub-resolved policy before propagation
- Confirm `hubTemplateOptions.serviceAccountName` has RBAC for lookups
- Test with `remediationAction: inform` first

**Kyverno/Gatekeeper duplicate inform policies**
- Expected when `informKyvernoPolicies` / `informGatekeeperPolicies` are true
- Set to `false` if you only want the constraint CR deployed

**Migrating from PolicyGenTemplate (PGT)**
- PGT used `bindingRules` → PlacementRule; PolicyGenerator uses `policyDefaults.placement` → Placement API
- See: [Migrate to RHACM Policy Generator (OCP 4.16)](https://developers.redhat.com/articles/2025/02/07/migrate-rhacm-policy-generator-openshift-416)

---

## References

- Config: `platform-config/acm/policies/`, `platform-config/clients/[client]/policies/`
- Generator reference: [policygenerator-reference.yaml](https://github.com/open-cluster-management-io/policy-generator-plugin/blob/main/docs/policygenerator-reference.yaml)
- Policy collection: [stolostron/policy-collection](https://github.com/stolostron/policy-collection)
- RHACM docs: [Governance 2.16](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.16/html/governance/governance) · [Template processing §1.2](https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/2.16/html/governance/governance#template-processing)
- Templating: [Tips Part 2 (object-templates-raw)](https://www.redhat.com/en/blog/tips-for-using-templating-in-governance-policies-part-2) · `policytools template-resolver` (RHACM 2.14+)
- Task: `tasks/policy-authoring`
- Troubleshooting: `troubleshooting/acm-policies`
- Placement: `acm/placement`
- Kustomize: `deploy/kustomize`
