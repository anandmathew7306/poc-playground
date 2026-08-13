# ocp-confluence-sync

Proof of concept: keep a Confluence Cloud page in sync with live OpenShift
cluster state, instead of manually re-scraping a datasheet that goes stale.

The POC reads a single value from a ConfigMap and publishes it to a demo
page. The production version would read real networking data (cluster/service
network CIDRs, SDN type, egress IPs, NetworkPolicies, Routes, ...) using the
same read -> format -> update loop.

## How it works

1. Read the source value from the cluster (`oc get cm ... -o jsonpath=...`).
2. `GET` the Confluence page with `expand=version,body.storage`.
3. If the page already shows the current value, exit without writing
   (idempotent — safe to run on a schedule).
4. Otherwise build a new storage-format body and `PUT` it with
   `version.number + 1` (Confluence returns 409 if the version is not
   incremented; fetching the version immediately before the PUT avoids this).

Cluster access is read-only. The only write anywhere is the page update.

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Network path to the Confluence Cloud site (a proxy via `https_proxy` works;
  `urllib` honours it, and `oc` is unaffected as long as the cluster domain is
  in `no_proxy`)
- A Confluence API token: id.atlassian.com -> Security -> API tokens

## Usage

```bash
cp env.example .env      # fill in real values -- .env is gitignored
set -a; . ./.env; set +a
python3 sync.py
```

Expected output on a change:

```
cluster value: <value>
page '<title>' at version N
page updated to version N+1
```

## Security / hygiene

- This repo is public: no site names, cluster hostnames, namespaces, page
  ids, emails, or tokens in any tracked file. All of that lives in `.env`
  (gitignored) or shell exports.
- The demo trigger is editing the source ConfigMap value
  (`oc set data cm/<name> <key>=<new-value>`) — an isolated, unmounted
  ConfigMap with zero blast radius. Production-affecting config (MetalLB,
  MTU, etc.) is explicitly not used as a trigger.

## Post-POC hardening (planned, not implemented)

- Cluster ServiceAccount with `get`/`list` only on the resources the real
  datasheet needs, instead of a personal login.
- Dedicated Confluence bot account scoped to the target space.
- Scheduling: CI job or OpenShift CronJob.
- Diff detection with Slack/email alert when content changes between syncs.
