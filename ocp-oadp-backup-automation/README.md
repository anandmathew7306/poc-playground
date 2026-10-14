# OADP backup automation by namespace label

Label a namespace `backup=true` and it gets its own daily and weekly OADP Schedule, plus a first backup straight away. Remove the label and its Schedules go away; past backups stay until they expire. No one writes Schedule YAML by hand.

Tested on single-node OpenShift 4.20 with OADP 1.5.8, LVM Storage and AWS S3. A lab to run it on: [`../ocp-sno-proxmox-lab`](../ocp-sno-proxmox-lab).

## How it works

```
namespace (backup=true) → CronJob (sync.sh, every minute) ─┬→ Schedules <ns>-daily / <ns>-weekly → Backup (on schedule)
                                                           └→ Backup <ns>-initial-<time>          (once, right away)
Backup → CSI disk snapshot → data mover (kopia) → S3
```

Each run of `sync.sh`:
1. Lists namespaces labelled `backup=true`.
2. Makes sure each has `<ns>-daily` and `<ns>-weekly` in `openshift-adp`, labelled `app.kubernetes.io/managed-by=label-scheduler`.
3. If the weekly Schedule was just created, creates one Backup `<ns>-initial-<UTC time>`. A new Schedule waits for its first cron time; this makes the namespace protected at once.
4. Deletes Schedules **it created** whose namespace is no longer labelled `true`. Hand-made Schedules are never touched.

Defaults (`label-scheduler-settings`, change without touching the script):

| | Daily | Weekly |
|---|---|---|
| Cron | `0 1 * * *` | `0 2 * * 6` |
| Disk snapshot | yes | yes |
| Copy to S3 (`snapshotMoveData`) | no: fast local restore point | yes: the off-site copy |
| TTL | 30h | 360h |

The service account can read namespaces, manage Schedules and **create** Backups in `openshift-adp`. It cannot read, change or delete Backups.

## Setup

**1. Storage.** A CSI StorageClass with a VolumeSnapshotClass. Mark the snapshot class for OADP:

```bash
oc label volumesnapshotclass <class> velero.io/csi-volumesnapshot-class=true
```

**2. S3 bucket and credentials.** A private bucket and a user that can only use that bucket ([`manifests/iam-policy.json`](manifests/iam-policy.json)). Write the access key straight to a file in the format OADP reads, so the secret never appears on screen:

```bash
aws s3api create-bucket --bucket <bucket-name> --region <aws-region> --create-bucket-configuration LocationConstraint=<aws-region>
aws iam create-user --user-name oadp-backup
aws iam put-user-policy --user-name oadp-backup --policy-name oadp-backup-bucket --policy-document file://manifests/iam-policy.json   # after filling in <bucket-name>
umask 077; aws iam create-access-key --user-name oadp-backup --query 'AccessKey.[AccessKeyId,SecretAccessKey]' --output text \
  | awk '{print "[default]\naws_access_key_id="$1"\naws_secret_access_key="$2}' > ~/oadp-cred
```

**3. OADP.**

```bash
oc get packagemanifest redhat-oadp-operator -n openshift-marketplace -o jsonpath='{range .status.channels[*]}{.name}{"  "}{.currentCSV}{"\n"}{end}'
oc apply -f manifests/oadp-operator.yaml
oc get csv -n openshift-adp                                   # Succeeded
oc create secret generic cloud-credentials -n openshift-adp --from-file cloud=$HOME/oadp-cred && rm ~/oadp-cred
oc apply -f manifests/dpa.yaml                                # after filling in bucket and region
oc get backupstoragelocation -n openshift-adp                 # Available
```

**4. Test a backup by hand** (optional):

```bash
oc apply -f manifests/demo-app.yaml
oc apply -f manifests/backup-test.yaml
oc get backup demo-app-test-1 -n openshift-adp -o custom-columns=PHASE:.status.phase,ITEMS:.status.progress.itemsBackedUp,ERRORS:.status.errors
oc get datauploads -n openshift-adp                           # Completed = disk data is in S3
```

**5. The automation.** Fill in `<cli-image>` in the CronJob first (command in the file), then:

```bash
oc apply -f manifests/automation-rbac.yaml -f manifests/automation-config.yaml -f manifests/automation-cronjob.yaml
oc auth can-i delete backups.velero.io -n openshift-adp --as system:serviceaccount:backup-automation:label-scheduler   # no
```

## Demo

```bash
oc label namespace demo-app backup=true
# about a minute later
oc logs -n backup-automation job/$(oc get jobs -n backup-automation -o jsonpath='{.items[-1:].metadata.name}')
#   create  demo-app-daily / create  demo-app-weekly / backup  demo-app-initial-…
oc get schedules,backups -n openshift-adp
oc label namespace demo-app backup-          # log shows delete; Schedules gone, backups stay
```

[`demo-flow.html`](demo-flow.html) is a click-through diagram of the same flow (Back/Next or arrow keys). [`scripts/reset-demo.sh`](scripts/reset-demo.sh) puts everything back to "nothing backed up" between runs:

```bash
API_SERVER=https://api.<cluster>.<domain>:6443 BUCKET=<bucket-name> PREFIX=velero ./scripts/reset-demo.sh
```

It removes the `backup` labels, the tool's Schedules and Backups, Velero's repository records and the objects under the bucket prefix. It refuses to run against any other API server, and asks before deleting.

## Things worth knowing

| Topic | Detail |
|---|---|
| New Schedule does not run at once | It waited for its first cron time in testing. Hence the initial backup. |
| Deleting backups | Use a `DeleteBackupRequest`. `oc delete backup` only removes the object; Velero syncs it back from S3. |
| What lands in S3 | `backups/<name>/`: objects, logs, metadata, one folder per backup. `kopia/<ns>/`: disk data, one de-duplicated, encrypted repository per namespace. |
| Snapshots after a move-data backup | Removed once the data is in S3. Snapshot-only (daily) backups keep their VolumeSnapshot until the backup expires. |
| Backup phase | `oc get backup` shows no phase by default; use `-o custom-columns=PHASE:.status.phase`. |
| MinIO in-cluster | Free MinIO images are no longer published (quay.io pull unauthorized, Docker Hub repo gone). Use another S3 or a cloud bucket. |
| Failed CronJob run | A run can fail if the API server is briefly unavailable; the next run fixes it, as each run checks everything from scratch. |
| Run interval | Every minute is demo pace. Something like `*/15 * * * *` is enough for real use. |

## Files

| File | What |
|---|---|
| `manifests/oadp-operator.yaml` | Namespace, OperatorGroup, Subscription |
| `manifests/dpa.yaml` | DataProtectionApplication with an S3 backup location |
| `manifests/iam-policy.json` | Bucket-only policy for the OADP user |
| `manifests/demo-app.yaml` | Test app with a 1 Gi disk |
| `manifests/backup-test.yaml` | One-off test backup |
| `manifests/automation-rbac.yaml` | Namespace `backup-automation`, service account, permissions |
| `manifests/automation-config.yaml` | Settings + `sync.sh` |
| `manifests/automation-cronjob.yaml` | The CronJob |
| `scripts/reset-demo.sh` | Reset to "nothing backed up" |
| `demo-flow.html` | Click-through diagram |
