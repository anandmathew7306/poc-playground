#!/usr/bin/env python3
"""
ocp-db-backup-check.py — read-only report of databases in OADP-scheduled
namespaces, the backup hooks around them, and the app's own dump jobs.

Sections:
  1. OADP Schedules: namespaces, cron, hooks in the Schedule spec
  2. Database pods in scheduled namespaces: image, PVCs, hook annotations
  3. CronJobs and recent Jobs in scheduled namespaces
  4. AAP (if its CRDs exist): platform health and backup records
  5. VolSync ReplicationSources / ReplicationDestinations in scheduled namespaces

A database pod is one where every container image looks like a database
(postgres, mysql, mongo, redis, ...). Pods where only some containers match
are listed as sidecars, not counted. Pods owned by a Job are dump jobs, not
databases. Standalone pods with no PVC are listed as clients.

Uses `oc get` and `oc whoami` only. Never reads Secrets, pod logs, or files
on disks. Does not print CronJob commands (they can carry credentials).

Requires: python3 + oc (logged in). Stdlib only.

Usage:
    python3 ocp-db-backup-check.py --server https://api.example:6443 > db-backup.md

Refuses to continue unless `oc whoami --show-server` matches --server.
Redirect stdout into a private notes repo. Do not commit live output here.
"""

from __future__ import print_function

import argparse
import datetime
import json
import re
import subprocess
import sys


DB_IMAGE = re.compile(r"postgres|postgresql|mysql|mariadb|mongo|redis|valkey|cassandra|mssql|oracle", re.I)
HELPER_IMAGE = re.compile(r"operator|pgbouncer|pgbackrest|exporter", re.I)
SECRETISH = re.compile(r"((?:pass(?:word)?|pwd|token|secret)[=: \"']+)[^ \"'&,]+", re.I)
HOOK_PREFIXES = ("pre.hook.backup.velero.io/", "post.hook.backup.velero.io/")
OADP_NS = "openshift-adp"
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


def oc_run(args):
    return subprocess.run(
        ["oc"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def oc_json(args, optional=False):
    p = oc_run(args + ["-o", "json"])
    if p.returncode != 0:
        if optional:
            return {"items": []}
        err = (p.stderr or p.stdout or "").strip().splitlines()
        die("oc {0} failed: {1}".format(" ".join(args), err[-1] if err else p.returncode))
    try:
        return json.loads(p.stdout)
    except ValueError:
        die("oc {0} did not return json".format(" ".join(args)))


def norm_server(url):
    return (url or "").strip().rstrip("/")


def md_table(headers, rows):
    if not rows:
        return "_no data_\n"
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join(["---"] * len(headers)) + "|"
    body = []
    for row in rows:
        cells = []
        for cell in row:
            text = "-" if cell in (None, "") else str(cell)
            text = text.replace("|", "\\|").replace("\n", " ")
            cells.append(text)
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([head, sep] + body) + "\n"


def redact(text):
    return SECRETISH.sub(r"\1REDACTED", text or "")


def parse_ts(ts):
    try:
        return datetime.datetime.strptime(ts, TS_FMT)
    except (TypeError, ValueError):
        return None


def duration(start, end):
    a, b = parse_ts(start), parse_ts(end)
    if not a or not b:
        return ""
    secs = int((b - a).total_seconds())
    if secs < 120:
        return "{0}s".format(secs)
    return "{0}m".format(secs // 60)


def conditions(obj):
    out = {}
    for c in (obj.get("status") or {}).get("conditions") or []:
        out[c.get("type")] = (c.get("status"), c.get("lastTransitionTime"))
    return out


def cond_text(conds, types):
    parts = []
    for t in types:
        if t in conds:
            parts.append("{0}={1} ({2})".format(t, conds[t][0], conds[t][1] or "-"))
    return ", ".join(parts)


def hook_annotations(meta):
    ann = meta.get("annotations") or {}
    return {k: v for k, v in ann.items() if k.startswith(HOOK_PREFIXES)}


def workload_of(pod, rs_owner):
    """Return (kind, name) of the controller that runs this pod."""
    refs = (pod.get("metadata") or {}).get("ownerReferences") or []
    if not refs:
        return "Pod", (pod.get("metadata") or {}).get("name")
    ref = refs[0]
    kind, name = ref.get("kind"), ref.get("name")
    if kind == "ReplicaSet" and name in rs_owner:
        return rs_owner[name]
    return kind, name


def crd_exists(name):
    return oc_run(["get", "crd", name, "-o", "name"]).returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Read-only database / hook / dump-job report")
    parser.add_argument("--server", required=True, help="API server URL that oc must already be logged into")
    args = parser.parse_args()

    expected = norm_server(args.server)
    who = oc_run(["whoami"])
    server = oc_run(["whoami", "--show-server"])
    if who.returncode != 0 or server.returncode != 0:
        die("oc whoami failed. Log in before running this script.")
    actual = norm_server(server.stdout)
    if actual != expected:
        die("refusing: oc server is {0}, --server is {1}".format(actual, expected))

    schedules = oc_json(["get", "schedules.velero.io", "-n", OADP_NS], optional=True).get("items") or []

    sched_rows = []
    namespaces = set()
    for s in sorted(schedules, key=lambda x: x["metadata"]["name"]):
        spec = s.get("spec") or {}
        tmpl = spec.get("template") or {}
        nss = tmpl.get("includedNamespaces") or []
        namespaces.update(nss)
        hooks = (tmpl.get("hooks") or {}).get("resources") or []
        hook_names = ", ".join(h.get("name") or "?" for h in hooks)
        sched_rows.append([
            s["metadata"]["name"], spec.get("schedule"), ", ".join(nss),
            len(hooks), hook_names, tmpl.get("snapshotMoveData"),
        ])
    namespaces = sorted(n for n in namespaces if n != "*")

    db_rows = []
    sidecar_rows = []
    client_rows = []
    other_hook_rows = []
    cron_rows = []
    job_rows = []
    db_ns = set()

    for ns in namespaces:
        pods = oc_json(["get", "pods", "-n", ns], optional=True).get("items") or []
        rss = oc_json(["get", "replicasets", "-n", ns], optional=True).get("items") or []
        rs_owner = {}
        for rs in rss:
            refs = (rs.get("metadata") or {}).get("ownerReferences") or []
            if refs:
                rs_owner[rs["metadata"]["name"]] = (refs[0].get("kind"), refs[0].get("name"))

        other_hooks = {}
        for pod in pods:
            meta = pod.get("metadata") or {}
            spec = pod.get("spec") or {}
            images = [c.get("image") or "" for c in spec.get("containers") or []]
            pvcs = [v["persistentVolumeClaim"].get("claimName") for v in spec.get("volumes") or []
                    if v.get("persistentVolumeClaim")]
            hooks = hook_annotations(meta)
            kind, wname = workload_of(pod, rs_owner)
            helpers = [i for i in images if HELPER_IMAGE.search(i)]
            main = [i for i in images if i not in helpers]
            matches = [i for i in main if DB_IMAGE.search(i)]
            short = ", ".join(sorted(set(i.split("@")[0].rsplit("/", 1)[-1] for i in matches)))

            if kind in ("Job", "CronJob"):
                continue
            if matches and len(matches) == len(main):
                if kind == "Pod" and not pvcs:
                    client_rows.append([ns, meta.get("name"), short])
                    continue
                db_ns.add(ns)
                pre = redact(hooks.get("pre.hook.backup.velero.io/command", ""))
                post = redact(hooks.get("post.hook.backup.velero.io/command", ""))
                db_rows.append([
                    ns, meta.get("name"), "{0}/{1}".format(kind, wname), short,
                    ", ".join(pvcs), pre, post,
                ])
            elif matches:
                sidecar_rows.append([ns, meta.get("name"), "{0}/{1}".format(kind, wname), short])
            elif hooks:
                cmd = redact(hooks.get("pre.hook.backup.velero.io/command", ""))
                first = cmd.strip("[]").split(",")[0].strip().strip('"') if cmd else "(no pre command)"
                other_hooks[first] = other_hooks.get(first, 0) + 1
        for first, count in sorted(other_hooks.items()):
            other_hook_rows.append([ns, first, count])

        cronjobs = oc_json(["get", "cronjobs", "-n", ns], optional=True).get("items") or []
        for cj in sorted(cronjobs, key=lambda x: x["metadata"]["name"]):
            spec = cj.get("spec") or {}
            st = cj.get("status") or {}
            pspec = (((spec.get("jobTemplate") or {}).get("spec") or {}).get("template") or {}).get("spec") or {}
            images = [c.get("image", "").split("@")[0].rsplit("/", 1)[-1] for c in pspec.get("containers") or []]
            vols = pspec.get("volumes") or []
            claims = [v["persistentVolumeClaim"].get("claimName") for v in vols if v.get("persistentVolumeClaim")]
            cms = [v["configMap"].get("name") for v in vols if v.get("configMap")]
            cron_rows.append([
                ns, cj["metadata"]["name"], spec.get("schedule"), spec.get("timeZone") or "UTC (controller)",
                spec.get("suspend"), st.get("lastScheduleTime"), st.get("lastSuccessfulTime"),
                ", ".join(images), ", ".join(claims), ", ".join(cms),
            ])

        jobs = oc_json(["get", "jobs", "-n", ns], optional=True).get("items") or []
        for job in sorted(jobs, key=lambda x: (x.get("status") or {}).get("startTime") or ""):
            st = job.get("status") or {}
            refs = (job.get("metadata") or {}).get("ownerReferences") or []
            owner = "{0}/{1}".format(refs[0].get("kind"), refs[0].get("name")) if refs else "-"
            job_rows.append([
                ns, job["metadata"]["name"], owner, st.get("startTime"), st.get("completionTime"),
                duration(st.get("startTime"), st.get("completionTime")),
                st.get("succeeded"), st.get("failed"),
            ])

    aap_rows = []
    aap_backup_rows = []
    aap_flags = []
    has_aap = crd_exists("ansibleautomationplatforms.aap.ansible.com")
    if has_aap:
        for inst in oc_json(["get", "ansibleautomationplatforms.aap.ansible.com", "-A"], optional=True).get("items") or []:
            meta = inst.get("metadata") or {}
            aap_rows.append([
                meta.get("namespace"), meta.get("name"),
                cond_text(conditions(inst), ["Running", "Successful", "Failure"]),
            ])
        backups = []
        if crd_exists("ansibleautomationplatformbackups.aap.ansible.com"):
            backups = oc_json(["get", "ansibleautomationplatformbackups.aap.ansible.com", "-A"], optional=True).get("items") or []
        latest = {}
        for b in sorted(backups, key=lambda x: x["metadata"].get("creationTimestamp") or ""):
            meta = b.get("metadata") or {}
            st = b.get("status") or {}
            conds = conditions(b)
            aap_backup_rows.append([
                meta.get("namespace"), meta.get("name"), meta.get("creationTimestamp"),
                (conds.get("Successful") or ("-",))[0], (conds.get("Failure") or ("-",))[0],
                st.get("backupClaim"), st.get("backupDirectory"),
            ])
            latest[meta.get("namespace")] = meta.get("creationTimestamp")
        aap_ns = set(r[0] for r in aap_rows)
        for row in cron_rows:
            ns, name, last_ok = row[0], row[1], row[6]
            if ns not in aap_ns or "backup" not in name or "prune" in name or "restore" in name:
                continue
            ok_ts, rec_ts = parse_ts(last_ok), parse_ts(latest.get(ns))
            if ok_ts and (not rec_ts or rec_ts < ok_ts - datetime.timedelta(hours=1)):
                aap_flags.append([
                    ns, name, last_ok, latest.get(ns) or "none",
                    "CronJob succeeded but no AAP backup record was created by that run",
                ])

    vs_rows = []
    for kind in ("replicationsources.volsync.backube", "replicationdestinations.volsync.backube"):
        if not crd_exists(kind):
            continue
        for obj in oc_json(["get", kind, "-A"], optional=True).get("items") or []:
            meta = obj.get("metadata") or {}
            if meta.get("namespace") not in namespaces:
                continue
            spec = obj.get("spec") or {}
            st = obj.get("status") or {}
            pvc = spec.get("sourcePVC") or ((spec.get("rsyncTLS") or {}).get("destinationPVC")) or ""
            trigger = (spec.get("trigger") or {}).get("schedule") or ("manual" if (spec.get("trigger") or {}).get("manual") else "")
            vs_rows.append([
                meta.get("namespace"), kind.split(".")[0][:-1], meta.get("name"), pvc, trigger,
                st.get("lastSyncTime"), st.get("lastSyncDuration"),
            ])

    print("# Databases, backup hooks, and dump jobs\n")
    print("Scope: namespaces named in OADP Schedules. Read-only `oc get`. "
          "A dump job's success is its Job status only; dump files on disk are not read.\n")
    print(md_table(["Item", "Value"], [
        ["user", (who.stdout or "").strip()],
        ["api", actual],
        ["OADP Schedules", len(schedules)],
        ["scheduled namespaces", len(namespaces)],
        ["namespaces with database pods", len(db_ns)],
        ["database pods", len(db_rows)],
        ["database pods with a hook annotation", len([r for r in db_rows if r[5] or r[6]])],
        ["Schedules with hooks in spec", len([r for r in sched_rows if r[3]])],
    ]))

    print("\n## 1. OADP Schedules\n")
    print(md_table(["Schedule", "Cron (UTC)", "Namespaces", "Hooks in spec", "Hook names", "snapshotMoveData"], sched_rows))

    print("\n## 2. Database pods\n")
    print(md_table(["Namespace", "Pod", "Controller", "DB image", "PVCs", "pre hook", "post hook"], db_rows))
    print("\n### Database container inside an app pod (sidecar, not counted)\n")
    print(md_table(["Namespace", "Pod", "Controller", "DB image"], sidecar_rows))
    print("\n### Standalone pods with a database image and no PVC (clients, not counted)\n")
    print(md_table(["Namespace", "Pod", "Image"], client_rows))
    print("\n### Other pods with backup hook annotations\n")
    print(md_table(["Namespace", "pre hook command", "Pods"], other_hook_rows))

    print("\n## 3. CronJobs and Jobs\n")
    print(md_table(["Namespace", "CronJob", "Schedule", "Time zone", "Suspend", "Last schedule", "Last success",
                    "Image", "PVCs", "ConfigMaps"], cron_rows))
    print("\n### Jobs still present\n")
    print(md_table(["Namespace", "Job", "Owner", "Start", "Done", "Took", "Succeeded", "Failed"], job_rows))

    print("\n## 4. AAP\n")
    if not has_aap:
        print("AAP CRDs not installed.\n")
    else:
        print(md_table(["Namespace", "Platform", "Conditions"], aap_rows))
        print("\n### AAP backup records\n")
        print(md_table(["Namespace", "Backup", "Created", "Successful", "Failure", "Backup PVC", "Directory"],
                       aap_backup_rows))
        print("\n### Flags\n")
        print(md_table(["Namespace", "CronJob", "Last success", "Latest backup record", "Note"], aap_flags))

    print("\n## 5. VolSync in scheduled namespaces\n")
    print(md_table(["Namespace", "Kind", "Name", "PVC", "Trigger", "Last sync", "Last duration"], vs_rows))


if __name__ == "__main__":
    main()
