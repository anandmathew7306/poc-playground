# ocp-metallb-stale-ads

Read-only check for two MetalLB cases:

- An ad names a pool or peer that is not on the cluster.
- A pool or peer is on the cluster, but no ad names it.

Pool, peer, and ad counts are not expected to match. One ad can name several pools and several peers. An empty list on an ad means every pool, or every peer. Those are not leftovers.

## Requirements

- `python3` (stdlib only)
- `oc` logged in to the cluster you want to check

Runs `oc get` and `oc whoami` only.

## Usage

```bash
python3 ocp-metallb-stale-ads.py
python3 ocp-metallb-stale-ads.py > stale-ads.md
```

The script is generic. The output names the cluster you are logged into. Save that output in a private notes repo. Do not commit live output here.
