---
name: tasks/policy-authoring
description: >
  Use when authoring or updating RHACM/Kyverno governance policies.
  Covers policy design, audit-then-enforce, and PolicySet integration.
status: active
reviewed_at: "2026-06-13"
version: 1.0.0
layer: tasks
refs:
  - core
  - acm/policies
  - acm/placement
  - deploy/kustomize
---

# Tasks/Policy Authoring

## When to Use
- New governance requirement for a client
- Prompt: `client: [name] | task: policy-authoring | policy: [what it enforces]`
- Converting audit findings into enforce policies
- SOC2/compliance-driven controls from `profile.yaml`

## How This Skill Composes
Policy mechanics live in `acm/policies` — this task skill defines the authoring workflow.

## Step 1 — Requirements
- [ ] Policy goal documented in ticket
- [ ] Compliance framework checked: `profile.yaml` → `compliance.frameworks`
- [ ] Remediation mode decided: `audit` first, then `enforce`
- [ ] Affected resources identified (Deployments, Services, Namespaces, etc.)

## Step 2 — Author policy manifest
Add to `platform-config/acm/policies/` or `clients/[client]/policies/`:
```yaml
# Example: require platform.io labels
apiVersion: policy.open-cluster-management.io/v1
kind: Policy
metadata:
  name: require-platform-labels
  namespace: open-cluster-management
spec:
  remediationAction: audit
  disabled: false
  policy-templates:
    - objectDefinition:
        apiVersion: policy.open-cluster-management.io/v1
        kind: ConfigurationPolicy
        metadata:
          name: require-platform-labels
        spec:
          remediationAction: audit
          severity: high
          object-templates:
            - complianceType: musthave
              objectDefinition:
                apiVersion: v1
                kind: Deployment
                metadata:
                  labels:
                    platform.io/client: "[client]"
```

## Step 3 — Validate locally
```bash
cd platform-config/acm/policies
kustomize build . > /tmp/policies.yaml
# Review rendered output; no secrets or client data in policy messages
```

## Step 4 — Add to client PolicySet
```bash
# clients/[client]/policies/kustomization.yaml must include new policy
# PolicySet [client]-policy-set must list the policy
oc get policyset [client]-policy-set -n open-cluster-management -o yaml
```

## Step 5 — Deploy via PR
- PR to platform-config: `feat: add [policy-name] policy for [client]`
- CI: kustomize build passes
- Apply on hub after merge (GitOps) or manual for urgent audit-only

## Step 6 — Verify compliance
```bash
oc get policy [policy-name] -n open-cluster-management
oc describe policy [policy-name] -n open-cluster-management
# Wait for compliance scan (~5-10 min)
```
Load `troubleshooting/acm-policies` if NonCompliant resources found.

## Step 7 — Promote audit → enforce
- [ ] Audit mode clean for 7 days (or client-agreed period)
- [ ] Client anchor approval for enforce
- [ ] Change `remediationAction: enforce` via PR
- [ ] Monitor for blocked deployments post-enforce

## Common Issues

**Policy matches too broadly**
- Scope with namespaceSelector or object labels
- Test on nonprod cluster first via Placement predicate

**Kyverno vs ConfigurationPolicy**
- Use Kyverno for mutation/validation; ConfigurationPolicy for must-have/must-not
- Do not duplicate same rule in both engines

**Client workloads blocked on enforce**
- Roll back to audit via PR immediately
- Fix manifests in `clients/[client]/kustomize/` per violation messages

## References
- ACM: `acm/policies`, `acm/placement`
- Security gates: `core`
- Runbook: `platform-ops/runbooks/acm/policy-noncompliant.md`
- Config: `platform-config/acm/policies/README.md`
