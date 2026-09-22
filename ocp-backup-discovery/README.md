# ocp-backup-discovery

Read-only **inventory** of OpenShift **OADP / Velero** backup (operator, DPA,
storage locations, schedules, recent Backup/Restore CRs, CSI snapshot classes,
VM coverage vs schedules, backup-related alerts).

etcd CronJobs, AAP’s own backup CronJobs, and VolSync are **presence only**
(parked — not the main report).

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Permission to `get`/`list` the objects below

**Read-only:** `oc get` / `oc whoami` only. Never apply/patch/delete.  
**Never reads Secrets.** S3 endpoints and other URL/IP-shaped values are
redacted in the printed BSL config.

## Usage

```bash
python3 ocp-backup-discovery.py
python3 ocp-backup-discovery.py > inventory.md
```

Save live output in a **private** notes repo. This directory is safe for
public repos (generic script only). Do not commit live dumps here.

## What it prints

| Section | Source |
|---|---|
| A identity | `whoami`, ClusterVersion |
| B OADP | DPA, CSV in DPA namespaces, node-agent / Velero pods |
| C locations | BackupStorageLocation, VolumeSnapshotLocation (endpoint values redacted) |
| D schedules | Velero Schedule cron, TTL, namespaces, snapshotMoveData, fs-backup |
| E backups | Backup phase counts + per-object phase / errors / hooks |
| F restores | Restore CR count + phases |
| G CSI / storage | StorageClass, VolumeSnapshotClass, VolumeSnapshot counts |
| H VMs vs schedules | VM count by namespace vs Schedule `includedNamespaces` |
| I alerts | PrometheusRules matching backup / oadp / velero / partial; flags whether `velero_backup_failure_total` and `velero_backup_partial_failure_total` appear in any expr |
| J parked | etcd-ish backup CronJobs, AAP-ish backup CronJobs, VolSync CR counts |

## Related

Platform etcd scripts and product-native backups (AAP, databases) are out of
scope except the parked presence check.
