---
title: "Client Offboarding"
type: "sop"
platform: "all"
last_updated: "2026-06-13"
author: "platrel"
---

# Client Offboarding SOP

Procedure for decommissioning a client from the PlatRel platform. Ensures clean removal of infrastructure, access, policies, and documentation with compliance-appropriate data handling.

## Prerequisites

- [ ] Offboarding ticket approved by client anchor and platform lead
- [ ] Data retention requirements confirmed with client (contractual minimum retention period)
- [ ] Client sign-off on decommission scope and timeline
- [ ] Final data export completed (if required)
- [ ] Billing/finance notified of decommission date
- [ ] Load client profile: `platform-config/clients/<client>/profile.yaml`

## Phase 1: Access and Alerting Teardown

### Step 1: Revoke Human Access

```bash
# List all RBAC bindings for client
oc get rolebindings,clusterrolebindings -A -o json | \
  jq '.items[] | select(.metadata.name | test("<client>"))'

# Remove client-specific ClusterRoleBindings
oc delete clusterrolebinding <client>-admin
oc delete clusterrolebinding <client>-view

# Revoke IdP group mappings (document in ticket — varies by IdP)
# Remove from GitLab group, PagerDuty schedule, Slack channels
```

### Step 2: Remove Alerting and Observability

```bash
# Remove Alertmanager routes for client
oc delete alertmanagerconfig <client>-alerts -n openshift-monitoring

# Remove PrometheusRules and ServiceMonitors
oc delete prometheusrule -n openshift-monitoring -l platform.io/client=<client>
oc delete servicemonitor -A -l platform.io/client=<client>

# Archive Grafana dashboards (export JSON, do not delete until sign-off)
```

## Phase 2: ACM and Policy Cleanup

### Step 3: Remove ACM Policies and Placement

```bash
# On ACM hub — remove client PolicySet
oc delete policyset <client>-policy-set -n open-cluster-management

# Remove Placement
oc delete placement <client>-placement -n open-cluster-management

# Verify no policies remain targeted (should show 0 clusters)
oc get policies -n open-cluster-management | grep <client>
```

### Step 4: Unregister Managed Clusters

```bash
# On spoke cluster — detach from hub
oc delete managedcluster <cluster-name> --ignore-not-found  # on hub
# On spoke:
oc delete klusterlet klusterlet -n open-cluster-management-agent --wait

# Verify removal on hub
oc get managedclusters | grep <client>
```

## Phase 3: Workload and Infrastructure Teardown

### Step 5: Delete Application Workloads

```bash
# Delete client namespaces (cascades workloads)
oc get namespaces -l platform.io/client=<client>
oc delete namespace <client-namespace> --wait=false

# Monitor termination — resolve finalizers if stuck
oc get namespace <client-namespace> -o json | jq '.spec.finalizers'
```

### Step 6: Decommission Clusters

**ROSA / ROSA HCP:**

```bash
# ROSA classic
rosa delete cluster --cluster <cluster-name> --yes

# ROSA HCP — delete HostedCluster on management cluster
oc delete hostedcluster <cluster-name> -n clusters-<name> --wait
oc delete nodepool <nodepool-name> -n clusters-<name>
```

**EKS:**

```bash
aws eks delete-nodegroup --cluster-name <cluster> --nodegroup-name <nodegroup>
aws eks delete-cluster --name <cluster-name>
```

**OCP (on-prem):**

```bash
# Follow vendor decommission procedure
# Destroy VMs / bare metal via IPI/UPI teardown
openshift-install destroy cluster --dir=<install-dir>
```

## Phase 4: Configuration and Documentation Cleanup

### Step 7: Remove platform-config Entries

Open PR in `platform-config` to delete:

- `clients/<client>/` (profile, kustomize, policies)
- `clusters/<client>-*/` (cluster-info, contacts)
- `slos/<client>.yaml`

### Step 8: Remove platform-skills Client Overlay

Open PR in `platform-skills` to delete:

- `.cursor/skills/clients/<client>/SKILL.md`

### Step 9: Archive platform-ops Artifacts

- Move client-specific runbook notes to `postmortems/` if incident-related
- Do not delete generic runbooks — they apply to all clients
- Update team runbook index

## Phase 5: Compliance and Sign-Off

### Step 10: Compliance Checklist

- [ ] Audit logs exported and retained per contract period
- [ ] Secrets rotated on shared infrastructure (if client had access)
- [ ] No client data remains in logs, backups, or ticket systems
- [ ] AWS/Azure resources confirmed deleted (no orphaned ELBs, EBS, IAM roles)
- [ ] DNS records removed
- [ ] Client anchor sign-off received

## Sign-Off

| Phase | Engineer | Date | Ticket |
|-------|----------|------|--------|
| Access revoked | | | |
| ACM cleanup | | | |
| Clusters decommissioned | | | |
| Config PRs merged | | | |
| Compliance verified | | | |
| Client sign-off | | | |

## Related

- Skill: core
- Skill: tasks/client-onboarding (reverse of onboarding)
- Skill: acm/policies
- SOP: sops/access-provisioning.md
- Config: platform-config/clients/_template/profile.yaml

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Complete client decommission checklist |
