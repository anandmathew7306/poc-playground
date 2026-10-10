# ocp-metallb-cleanup-check

Read-only facts for a MetalLB cleanup on one cluster: what is stale, what is
left over, whether anything still depends on it, and how the live objects
compare with Git.

## Report

1. **Summary** counts
2. **Stale ads**: ads that name a pool or peer that is not on the cluster.
   Shows the references that still work, so the fix can be "delete the ad"
   or "edit the ad", and whether those pools are also selected by another ad
3. **Leftover pools**: pools no ad selects. Shows services that hold an IP
   from the pool or ask for it
4. **Leftover peers**: peers no BGP ad names, with BGP session state per node
   (`BGPSessionState`, when the cluster has it)
5. **LoadBalancer services with no IP**, and the pool they ask for
6. **Git vs live**: pools, peers and ads in Git (`--git`) or in the ACM
   policy copies on the cluster, compared with the live objects

Ad rules follow MetalLB: no pools and no pool selectors means every pool;
no peers on a BGP ad means every peer; pool selectors are matched against
pool labels.

## Requirements

- `python3`, stdlib only for the cluster read
- PyYAML only when `--git` is used
- `oc` already logged in, with permission to `get` MetalLB objects,
  Services, BGPSessionStates and ACM Policies

Uses `oc get` and `oc whoami` only. Never reads Secrets. Never prints peer
passwords, addresses or prefixes; only object names, VRF names and counts.

## Usage

```bash
python3 ocp-metallb-cleanup-check.py --server https://api.example:6443 > metallb.md
python3 ocp-metallb-cleanup-check.py --server https://api.example:6443 \
    --git /path/to/repo/env/policygentemplates > metallb.md
```

The script exits before any other read if `oc whoami --show-server` is not
`--server`.

`--git` reads the PolicyGenTemplates listed under `generators` in
`kustomization.yml` and skips the ones bound to another cluster by the same
label as this cluster's own PolicyGenTemplate.

Save live output in a **private** notes repo. This directory is safe for
public repos (generic script only). Do not commit live dumps here.

## Limits

- Facts only. It does not decide what to delete.
- A service's pool is read from the `ip-allocated-from-pool` annotation, or
  matched by address when the annotation is missing.
- BGP sessions are matched to peers by address and VRF. Sessions that match
  no BGPPeer are counted, not expanded.
