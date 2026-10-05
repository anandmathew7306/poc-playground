# ocp-db-backup-check

Read-only report of databases in OADP-scheduled namespaces, backup hooks
around them, and the app's own dump jobs.

A database pod is one where every non-helper container image looks like a
database (`postgres`, `mysql`, `mongo`, `redis`, and similar). Operator,
pgBouncer, pgBackRest, and exporter images are helpers, not databases.
Pods where only some containers match are listed as sidecars. Standalone
pods with no PVC are listed as clients. Job pods are not databases.

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` already logged in
- Permission to `get` Schedules, Pods, CronJobs, Jobs, ReplicaSets,
  AAP CRs (if present), and VolSync CRs (if present)

Uses `oc get` and `oc whoami` only. Never reads Secrets, pod logs, or
files on disks. Does not print CronJob commands.

## Usage

```bash
python3 ocp-db-backup-check.py --server https://api.example:6443
python3 ocp-db-backup-check.py --server https://api.example:6443 > db-backup.md
```

The script exits before any other read if `oc whoami --show-server` is not
`--server`.

Save live output in a **private** notes repo. This directory is safe for
public repos (generic script only). Do not commit live dumps here.

## Limits

- Dump files on disk are not read. A CronJob success is the Job status only.
- AAP "job succeeded but no backup record" is inferred from timestamps.
- Database operator backup settings (CloudNativePG, Crunchy) are not read.
- VM-inside databases are not detected.
