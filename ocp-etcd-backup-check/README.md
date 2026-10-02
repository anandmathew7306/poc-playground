# ocp-etcd-backup-check

Read-only report of one etcd backup CronJob: schedule, script hash, retained
Jobs and Pods, the files currently on the NFS share, and PrometheusRules that
name this job.

The file list is a read-only mount (`-o ro`) inside one short-lived debug pod
on a control-plane node. The script unmounts before that pod is removed. It
does not read Pod logs, does not create directories, and does not run the
backup script.

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` already logged in to the target cluster
- Permission to `get` the CronJob, ConfigMap, Jobs, Pods, Nodes, and PrometheusRules
- Permission to `oc debug` a control-plane node. That creates a pod and removes it when the command finishes

**No writes to the share.** The mount is `-o ro`, then `ls`, then `umount`. Never reads Secrets.
Env values whose names look like a secret are redacted.

## Usage

```bash
python3 ocp-etcd-backup-check.py --server https://api.example:6443
python3 ocp-etcd-backup-check.py --server https://api.example:6443 > etcd-report.md
```

The script exits before any other read if `oc whoami --show-server` is not
`--server`.

Save live output in a **private** notes repo. This directory is safe for
public repos (generic script only). Do not commit live dumps here.

Optional flags: `--namespace`, `--cronjob`, `--script-key`. Defaults are
`ocp-backup-etcd`, `openshift-backup`, and `backup.sh`.
