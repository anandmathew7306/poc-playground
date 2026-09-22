# ocp-oadp-restore-check

Read-only **second pass** after `ocp-backup-discovery`. Focuses on things the
inventory script does not print:

- Schedule include / exclude filters and hooks
- Backup hook / error fields on the CR
- DataUpload phases (weekly copy)
- VolumeSnapshots still on the cluster vs Backup names
- Restore and DataProtectionTest counts

Does **not** create a Restore. Does **not** read Secrets or Velero logs from S3.

## Requirements

- `python3` (stdlib only)
- `oc` logged in
- Read-only: `oc get` / `oc whoami` only

The `velero` CLI is **not** required. `velero get backup` and
`oc get backup -n openshift-adp` are the same objects.

## Usage

```bash
python3 ocp-oadp-restore-check.py
python3 ocp-oadp-restore-check.py > restore-check.md
```

Save live output in a **private** notes repo. Do not commit dumps here.
