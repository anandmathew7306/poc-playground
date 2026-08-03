---
title: "Access Provisioning"
type: "sop"
platform: "all"
last_updated: "2026-06-13"
author: "platrel"
---

# Access Provisioning SOP

Procedure for granting and revoking cluster access for engineers, client contacts, and automation service accounts. All access requires a ticket reference and follows least-privilege principles.

## Prerequisites

- [ ] Access request ticket with manager approval (and client approval for client clusters)
- [ ] Request specifies: user identity, cluster(s), access level, duration, justification
- [ ] User exists in corporate IdP (LDAP/OIDC group)
- [ ] Load client profile for terminology and compliance gates: `platform-config/clients/<client>/profile.yaml`
- [ ] SOC2/compliance clusters: no cluster-admin to client contacts without security review

## Access Levels

| Level | Scope | Typical Use |
|-------|-------|-------------|
| `view` | Read-only cluster-wide | Client stakeholders, auditors |
| `edit` | Read/write in named namespaces | Application developers |
| `admin` | Full access in named namespaces | Client platform engineers |
| `cluster-admin` | Cluster-wide admin | PlatRel SRE only — time-limited |

## Steps — Human Access (RBAC)

### Step 1: Verify Identity and Group Membership

```bash
# Confirm user is in the correct IdP group
# Groups follow pattern: platrel-<client>-<level>
# Example: platrel-acme-edit, platrel-acme-view

# Verify group exists in cluster OAuth config
oc get oauth cluster -o yaml | grep -A5 groups
```

### Step 2: Create Namespace-Scoped Access (Preferred)

```bash
# Create RoleBinding for edit access in client namespace
cat <<EOF | oc apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: <user>-edit
  namespace: <client-namespace>
  labels:
    platform.io/client: <client>
    platform.io/team: platrel
subjects:
  - kind: Group
    apiGroup: rbac.authorization.k8s.io
    name: platrel-<client>-edit
roleRef:
  kind: ClusterRole
  name: edit
  apiGroup: rbac.authorization.k8s.io
EOF
```

### Step 3: Create Cluster-Scoped Access (PlatRel SRE Only)

```bash
# Time-limited cluster-admin for PlatRel engineers
cat <<EOF | oc apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: <user>-cluster-admin
  labels:
    platform.io/client: <client>
    platform.io/team: platrel
  annotations:
    platform.io/ticket: "<ticket-id>"
    platform.io/expires: "<YYYY-MM-DD>"
subjects:
  - kind: User
    apiGroup: rbac.authorization.k8s.io
    name: <user>@<domain>
roleRef:
  kind: ClusterRole
  name: cluster-admin
  apiGroup: rbac.authorization.k8s.io
EOF
```

### Step 4: Verify Access

```bash
# As the requesting user (or via impersonation with approval)
oc auth can-i get pods -n <client-namespace> --as=<user>@<domain>
oc auth can-i create deployments -n <client-namespace> --as=<user>@<domain>

# List effective permissions
oc describe rolebinding -n <client-namespace> <user>-edit
```

## Steps — Kubeconfig Access

### Step 5: Issue Kubeconfig (Break-Glass or Automation)

```bash
# Preferred: user authenticates via oc login / OIDC
oc login <api-server-url> --token=<oidc-token>

# For automation service accounts — create dedicated SA
oc create serviceaccount <sa-name> -n <client-namespace>
oc create rolebinding <sa-name>-edit \
  --serviceaccount=<client-namespace>:<sa-name> \
  --clusterrole=edit -n <client-namespace>

# Extract long-lived token (Kubernetes 1.24+)
oc create token <sa-name> -n <client-namespace> --duration=8760h

# Build kubeconfig
oc config set-cluster <cluster-name> --server=<api-url> --certificate-authority=<ca-file>
oc config set-credentials <sa-name> --token=<token>
oc config set-context <context> --cluster=<cluster-name> --user=<sa-name> --namespace=<client-namespace>
```

Store kubeconfig in approved secret manager — never in Git, Slack, or tickets.

## Steps — Access Revocation

```bash
# Remove RoleBinding or ClusterRoleBinding
oc delete rolebinding <user>-edit -n <client-namespace>
oc delete clusterrolebinding <user>-cluster-admin

# Revoke service account token
oc delete serviceaccount <sa-name> -n <client-namespace>

# Remove from IdP group (source of truth for human access)
# Document revocation in ticket
```

## ACM Hub Access

```bash
# Hub cluster access follows same RBAC pattern
# ACM console access is tied to OpenShift OAuth — no separate credential

# For managed cluster access via ACM console
oc get managedcluster <cluster-name>
# User needs view permission on ManagedCluster resource
```

## Compliance Gates

- [ ] Ticket reference annotated on all ClusterRoleBindings
- [ ] No `cluster-admin` granted to non-PlatRel users on SOC2 clusters
- [ ] Access reviewed quarterly — run access audit script
- [ ] Expired bindings removed within 24h of expiry date
- [ ] All access changes logged in audit trail

## Sign-Off

| Step | Engineer | Date | Ticket |
|------|----------|------|--------|
| Request validated | | | |
| RBAC applied | | | |
| Access verified | | | |
| Requester notified | | | |

## Related

- Skill: core (security gates, break-glass procedure)
- Skill: tasks/client-onboarding (Step 2 — access verification)
- SOP: sops/client-offboarding.md (access revocation)
- SOP: sops/certificate-rotation.md

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Complete RBAC and kubeconfig access procedure |
