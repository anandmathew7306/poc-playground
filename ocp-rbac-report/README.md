# ocp-rbac-report

Generates an **RBAC** reference report (markdown) for an OpenShift cluster.

## Scope

**In scope**

| Section | Source |
|---|---|
| Summary counts | ClusterRoles, ClusterRoleBindings, Roles, RoleBindings |
| Elevated focus | CRBs for `cluster-admin` / `admin` / `system:admin` (+ wildcard `*/*` ClusterRoles) |
| CRB subject rollup | Users / Groups / ServiceAccounts appearing in ClusterRoleBindings |
| ClusterRoleBindings | All |
| RoleBindings | All (`-A`) |
| ClusterRoles | Compact inventory (not full rule dump) |
| Roles | Per-namespace counts + name sample |

**Out of scope**

- ACM / PolicyGenTemplate compliance (needs hub)
- Identity provider config (`OAuth`, LDAP group sync details)
- Mutating cluster changes (this tool is read-only)

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Read access to cluster/namespaced RBAC

**Read-only:** only runs `oc get` / `oc whoami`. Never apply/patch/delete.

## Usage

```bash
# full scrape
python3 ocp-rbac-report.py
python3 ocp-rbac-report.py > rbac-<env>-<domain>-<site>.report.md

# call-ready elevated subset (same scrape path, filtered output)
python3 ocp-rbac-report.py --focus elevated
python3 ocp-rbac-report.py --focus elevated > rbac-<env>-<domain>-<site>.elevated.md

# customize elevated ClusterRole names
python3 ocp-rbac-report.py --elevated-roles cluster-admin,admin,edit
```

Save live output that contains cluster identity or user/group names into a
**private** notes repo. This directory is safe for public repos (generic
script only).

## Review hints

- Many `cluster-admin` subjects (Users/Groups/SAs) → privilege sprawl; GitOps
  cannot stay authoritative.
- Prefer Group subjects over individual Users when assessing IdP-driven access.
- Platform SAs with elevated CRBs deserve a separate look from human users.
- `RoleBindings` volume is high on busy clusters — use elevated focus first for
  the client narrative, then full report for deep dive.
