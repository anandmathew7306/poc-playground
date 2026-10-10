# ocp-operator-coverage-check

Read-only report of which added operators an ACM policy installs and
configures on one managed cluster, optionally compared with the
PolicyGenTemplates in Git.

Works without ACM hub access: it reads the Policy copies the hub placed on
the managed cluster, including their mode and compliance status.

## Categories

| Category | Meaning |
|---|---|
| ACM policy: install + config | A policy installs the operator and creates its custom resources |
| ACM policy: install only | A policy installs the operator, no custom resources in a policy |
| Other | Not installed by a policy (Argo CD, manual, ACM add-on, unknown) |

Extra columns are facts, not conclusions: policy mode (inform / enforce),
policy compliance, violation clauses that name the operator's Subscription
or custom resources, Argo CD label / ACM add-on, and with `--git` whether
Git installs and configures it plus the Git channel.

## Report

1. Summary counts per category, number of policies and NonCompliant policies
2. One row per installed operator
3. Policies on the cluster: mode, status, violation clauses, template kinds
   not expanded (`object-templates-raw`, `OperatorPolicy`, ...)
4. Git vs cluster (with `--git`): operators in Git but not installed, policy
   installs not in Git, channel differences, Git policies with no copy on
   the cluster
5. Subscriptions not counted (no CSV)

## Requirements

- `python3`, stdlib only for the cluster read
- PyYAML only when `--git` is used
- `oc` already logged in, with permission to `get` Subscriptions, OLM
  Operators, CRDs, Policies, AppliedManifestWorks and Deployments

Uses `oc get` and `oc whoami` only. Never reads Secrets. Prints kinds,
names, namespaces and channels only, never object values.

## Usage

```bash
python3 ocp-operator-coverage-check.py --server https://api.example:6443 > operators.md
python3 ocp-operator-coverage-check.py --server https://api.example:6443 \
    --git /path/to/repo/env/policygentemplates > operators.md
```

The script exits before any other read if `oc whoami --show-server` is not
`--server`.

`--git` reads the PolicyGenTemplates listed under `generators` in
`kustomization.yml`. A PolicyGenTemplate named after another cluster and
bound by that name is skipped. The cluster name is the namespace of the
Policy copies on the cluster.

Save live output in a **private** notes repo. This directory is safe for
public repos (generic script only). Do not commit live dumps here.

## Limits

- Only `object-templates` are expanded. Raw templates and `OperatorPolicy`
  are listed, not read.
- Config means the policy creates a kind this operator's CRDs define.
  Settings held in ConfigMaps or other generic objects are not counted.
- Policy status is whatever the hub last synced to the cluster copy. Without
  hub access, placement rules and history are not visible.
- `inform` policies report drift and do not fix it.
