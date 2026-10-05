# ocp-operator-policy-check

Read-only report of which added operators an ACM policy installs and
configures on one managed cluster, and which ones have no policy.

**Installed** means an OLM Subscription whose installed CSV is still present,
or an operator Deployment that a policy creates (for operators not installed
through OLM). A Subscription that names a CSV that no longer exists is listed
separately, not counted.

**Coverage** comes from the ACM Policies replicated onto the managed cluster.
That is what the hub actually placed there. A policy object is matched to an
operator by package name and namespace. Config objects are matched when their
kind belongs to a CRD the operator owns.

For installs outside policy, the source column shows an Argo CD tracking id,
an ACM add-on (AppliedManifestWork), or `none found`.

Platform operators (`oc get clusteroperators`) ship with OpenShift and are not
counted. `oc get operators` includes leftovers from removed installs. Those
are listed at the end.

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` already logged in to the managed cluster
- Permission to `get` Subscriptions, OLM Operators, ACM Policies,
  AppliedManifestWorks, CRDs, Deployments, and ClusterOperators

Uses `oc get` and `oc whoami` only. Never reads Secrets.

## Usage

```bash
python3 ocp-operator-policy-check.py --server https://api.example:6443
python3 ocp-operator-policy-check.py --server https://api.example:6443 > operators.md
```

The script exits before any other read if `oc whoami --show-server` is not
`--server`.

Save live output in a **private** notes repo. This directory is safe for
public repos (generic script only). Do not commit live dumps here.

## Limits

- Object templates given as a raw string (`object-templates-raw`) are not parsed.
- An operator installed by Helm or plain manifests, with no policy, is not found.
- A matching policy means a policy exists. With `inform` it reports drift and
  does not fix it.
