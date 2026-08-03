---
title: "Cluster Upgrade"
type: "sop"
platform: "ocp | rosa | rosa-hcp"
last_updated: "2026-06-13"
author: "platrel"
---

# Cluster Upgrade SOP

Standard operating procedure for upgrading OpenShift Container Platform (OCP), ROSA, and ROSA HCP clusters. Applies to all PlatRel-managed clusters. Load the client profile and platform skill before starting.

## Prerequisites

- [ ] Change ticket approved with maintenance window (client-facing: "platform maintenance window")
- [ ] Cluster health check passed — run `client: <name> | task: platform-health-check`
- [ ] Rollback plan documented (target version N-1 verified available)
- [ ] Stakeholders notified per `platform-config/clusters/<cluster>/contacts.yaml`
- [ ] Alertmanager silence created for expected upgrade alerts (max 4h, ticket reference required)
- [ ] Platform skill loaded: `platform/ocp`, `platform/rosa`, or `platform/rosa-hcp`
- [ ] Backup verified: etcd snapshot (OCP on-prem), Velero (if configured), ACM backup (hub)

## Pre-Upgrade Checks

```bash
# Verify cluster identity and current version
oc whoami
oc get clusterversion
oc get clusteroperators | grep -i false

# Verify no nodes NotReady
oc get nodes

# Verify etcd healthy (OCP)
oc get clusteroperator etcd

# For ROSA/ROSA HCP — check available upgrade paths
rosa describe cluster --cluster <cluster-name>
oc get hostedcluster -n clusters-<name> -o jsonpath='{.items[0].status.version}'  # HCP
```

Record baseline: cluster version, operator health, node count, and active alerts.

## Upgrade Steps — OCP (Self-Managed)

### Step 1: Update Channel and Pause Operators (if required)

```bash
# Review available updates
oc adm upgrade

# Set channel to match target (e.g., stable-4.16)
oc patch clusterversion version --type=merge -p '{"spec":{"channel":"stable-4.16"}}'
```

### Step 2: Start Control Plane Upgrade

```bash
# Apply upgrade to target version
oc adm upgrade --to=<target-version>

# Monitor progress
oc adm upgrade
oc get clusterversion -w
oc get clusteroperators -w
```

### Step 3: Monitor Machine Config Pool Rollout

```bash
# Watch MCP until all pools report UPDATED=True
oc get machineconfigpool -w

# Verify all nodes on new config version
oc get nodes -o json | jq -r '.items[] | "\(.metadata.name) \(.metadata.annotations["machineconfiguration.openshift.io/currentConfig"])"'
```

### Step 4: Post-Upgrade Validation

```bash
# All operators must be Available=True, Degraded=False
oc get clusteroperators

# Run health check
# client: <name> | task: platform-health-check

# Expire maintenance silence
# amtool silence expire <silence-id>
```

## Upgrade Steps — ROSA (Classic)

### Step 1: Initiate Upgrade via ROSA CLI

```bash
# Check available versions
rosa list upgrades --cluster <cluster-name>

# Schedule upgrade (immediate or at maintenance window)
rosa upgrade cluster --cluster <cluster-name> --version <target-version> --mode auto

# Monitor status
rosa describe cluster --cluster <cluster-name>
watch rosa list upgrades --cluster <cluster-name>
```

### Step 2: Monitor In-Cluster Operators

```bash
oc get clusterversion -w
oc get clusteroperators | grep -i false
oc get machineconfigpool -w
```

### Step 3: Verify Managed Add-ons

```bash
rosa list addons --cluster <cluster-name>
# Upgrade incompatible add-ons before or after cluster upgrade per compatibility matrix
rosa install addon --cluster <cluster-name> <addon-id> --version <version>
```

## Upgrade Steps — ROSA HCP (Hosted Control Planes)

### Step 1: Upgrade Hosted Cluster Control Plane

```bash
# On management cluster — check current version
oc get hostedcluster <cluster-name> -n clusters-<name> -o jsonpath='{.status.version}'

# Patch target version
oc patch hostedcluster <cluster-name> -n clusters-<name> --type=merge \
  -p '{"spec":{"channel":"stable-4.16","release":{"image":"<release-image>"}}}'

# Monitor control plane upgrade
oc get hostedcluster <cluster-name> -n clusters-<name> -w
```

### Step 2: Upgrade NodePools

```bash
# Upgrade worker nodes after control plane is complete
oc patch nodepool <nodepool-name> -n clusters-<name> --type=merge \
  -p '{"spec":{"release":{"image":"<release-image>"}}}'

oc get nodepool <nodepool-name> -n clusters-<name> -w
```

### Step 3: Validate Hosted Cluster

```bash
oc get hostedcluster <cluster-name> -n clusters-<name>
oc get nodepool -n clusters-<name>
# Log into hosted cluster and verify operators
oc get clusteroperators
```

## Rollback

### OCP Rollback

```bash
# Only possible if previous version still available in cluster
oc adm upgrade --to=<previous-version>
# If rollback fails, restore from etcd backup — escalate immediately
```

### ROSA Rollback

```bash
# ROSA does not support in-place downgrade
# Mitigation: restore workloads to standby cluster at previous version
# Open Red Hat support case for guidance
rosa create cluster --version <previous-version>  # standby approach
```

### ROSA HCP Rollback

```bash
# HostedCluster downgrade is not supported
# Failover to DR cluster documented in client profile
# Escalate to platform lead and Red Hat support
```

## Sign-Off

| Step | Engineer | Date | Ticket |
|------|----------|------|--------|
| Pre-checks complete | | | |
| Upgrade initiated | | | |
| Post-validation passed | | | |
| Silence expired | | | |
| Stakeholders notified | | | |

## Related

- Skill: platform/ocp, platform/rosa, platform/rosa-hcp
- Skill: tasks/platform-health-check
- Runbook: runbooks/ocp/operator-degraded.md
- Runbook: runbooks/ocp/mco-stuck.md
- Runbook: runbooks/rosa-hcp/hostedcluster-degraded.md
- SOP: sops/certificate-rotation.md

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Complete OCP/ROSA/ROSA HCP upgrade procedure |
