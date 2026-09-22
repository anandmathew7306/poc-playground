#!/usr/bin/env python3
"""
ocp-oadp-restore-check.py — read-only restore-readiness extras for OADP.

Separate from ocp-backup-discovery. This pass looks at Schedule filters,
Backup hook/error fields, DataUploads, leftover VolumeSnapshots, and
Restore / DataProtectionTest objects.

Read-only. `oc get` / `oc whoami` only. Never reads Secrets.
Does not run `velero` (optional CLI; same CRs via oc).
Does not create a Restore or download backup logs from object storage.

Usage:
    python3 ocp-oadp-restore-check.py
    python3 ocp-oadp-restore-check.py > restore-check.md
"""

from __future__ import print_function

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime


URL_OR_IP_RE = re.compile(
    r"https?://|\b\d{1,3}(?:\.\d{1,3}){3}\b",
    re.I,
)


def oc_run(args):
    return subprocess.run(
        ["oc"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=False,
    )


def oc_text(args):
    return (oc_run(args).stdout or "").strip()


def kind_missing(err):
    e = (err or "").lower()
    return "doesn't have a resource type" in e or "not found" in e


def oc_list(args):
    p = oc_run(args + ["-o", "json"])
    if p.returncode != 0:
        err = (p.stderr or "").strip()
        if kind_missing(err):
            return []
        print("  > failed: oc {0}".format(" ".join(args)), file=sys.stderr)
        if err:
            print("  > {0}".format(err.splitlines()[-1]), file=sys.stderr)
        return None
    try:
        return (json.loads(p.stdout) or {}).get("items") or []
    except ValueError:
        return None


def md_table(headers, rows):
    if not rows:
        return "_no data_\n"
    h = "| " + " | ".join(headers) + " |"
    s = "|" + "|".join(["---"] * len(headers)) + "|"
    r = []
    for row in rows:
        cells = []
        for c in row:
            t = "-" if c in (None, "") else str(c)
            t = t.replace("|", "/").replace("\n", " ")
            cells.append(t)
        r.append("| " + " | ".join(cells) + " |")
    return "\n".join([h, s] + r) + "\n"


def join_list(value):
    if not value:
        return "-"
    if isinstance(value, list):
        return ", ".join(str(x) for x in value) or "-"
    return str(value)


def short(value, limit=80):
    if value in (None, "", [], {}):
        return "-"
    if isinstance(value, (list, dict)):
        s = json.dumps(value, sort_keys=True)
    else:
        s = str(value)
    if URL_OR_IP_RE.search(s):
        return "<redacted>"
    if len(s) > limit:
        return s[: limit - 3] + "..."
    return s


def labels(md):
    return (md or {}).get("labels") or {}


def anns(md):
    return (md or {}).get("annotations") or {}


def section_a():
    print("## A — identity\n")
    print(md_table(
        ["Item", "Value"],
        [
            ["user", oc_text(["whoami"]) or "(whoami failed)"],
            ["api", oc_text(["whoami", "--show-server"]) or "-"],
            ["velero CLI", "not used (oc only)"],
        ],
    ))


def section_b():
    print("## B — Schedule filters and hooks\n")
    print("Empty include/exclude usually means Velero default: all resource "
          "types in `includedNamespaces`.\n")
    items = oc_list(["get", "schedule.velero.io", "-A"])
    if items is None:
        print("_could not list Schedules._\n")
        return
    rows = []
    for it in items:
        md = it.get("metadata") or {}
        spec = it.get("spec") or {}
        tmpl = spec.get("template") or {}
        rows.append([
            md.get("namespace") or "-",
            md.get("name") or "-",
            join_list(tmpl.get("includedNamespaces")),
            join_list(tmpl.get("excludedNamespaces")),
            join_list(tmpl.get("includedResources")),
            join_list(tmpl.get("excludedResources")),
            tmpl.get("includeClusterResources"),
            short(tmpl.get("labelSelector")),
            short(tmpl.get("hooks")),
            tmpl.get("ttl") or "-",
            tmpl.get("snapshotMoveData"),
        ])
    print(md_table(
        ["NS", "Schedule", "Included NS", "Excluded NS", "Included resources",
         "Excluded resources", "Cluster resources", "Label selector", "Hooks",
         "TTL", "Move data"],
        rows,
    ))


def section_c():
    print("## C — Backup CR hook / error fields\n")
    print("This is what is **on the Backup object**. Hook command text often "
          "lives on the workload (pod annotations) or in Velero logs on S3 — "
          "those are not read here.\n")
    items = oc_list(["get", "backups.velero.io", "-A"])
    if items is None:
        print("_could not list Backups._\n")
        return []
    rows = []
    for it in items:
        md = it.get("metadata") or {}
        spec = it.get("spec") or {}
        st = it.get("status") or {}
        hooks = st.get("hookStatus") or {}
        rows.append([
            md.get("name") or "-",
            st.get("phase") or "-",
            st.get("errors") if st.get("errors") is not None else "-",
            "{0}/{1}".format(
                hooks.get("hooksFailed") if hooks.get("hooksFailed") is not None else 0,
                hooks.get("hooksAttempted") if hooks.get("hooksAttempted") is not None else 0,
            ),
            short(spec.get("hooks")),
            short(st.get("validationErrors")),
            short(st.get("failureReason")),
            spec.get("snapshotMoveData"),
            spec.get("ttl") or "-",
            st.get("completionTimestamp") or "-",
        ])
    rows.sort(key=lambda r: r[9], reverse=True)
    print(md_table(
        ["Backup", "Phase", "Errors", "Hooks fail/try", "Spec hooks",
         "validationErrors", "failureReason", "Move data", "TTL", "Ended"],
        rows,
    ))
    return items


def section_d():
    print("## D — DataUpload (weekly copy / snapshotMoveData)\n")
    items = oc_list(["get", "dataupload.velero.io", "-A"])
    if items is None:
        print("_could not list DataUploads (kind missing or get failed)._\n")
        return
    print("Count: **{0}**\n".format(len(items)))
    phases = Counter((it.get("status") or {}).get("phase") or "Unknown"
                     for it in items)
    print(md_table(
        ["Phase", "Count"],
        [[p, str(n)] for p, n in phases.most_common()],
    ))
    rows = []
    for it in items:
        md = it.get("metadata") or {}
        spec = it.get("spec") or {}
        st = it.get("status") or {}
        rows.append([
            md.get("namespace") or "-",
            md.get("name") or "-",
            labels(md).get("velero.io/backup-name") or "-",
            spec.get("sourceNamespace") or "-",
            short(spec.get("sourcePVCName") or spec.get("pvc") or
                  (spec.get("csiSnapshot") or {}).get("volumeSnapshotName"),
                  40),
            st.get("phase") or "-",
            short(st.get("progress")),
            short(st.get("message"), 60),
        ])
    rows.sort(key=lambda r: r[2])
    print(md_table(
        ["NS", "DataUpload", "Backup", "Source NS", "PVC / snap", "Phase",
         "Progress", "Message"],
        rows,
    ))


def section_e(backups):
    print("## E — VolumeSnapshots still on the cluster\n")
    print("Daily Backups have a short TTL. If the snapshot class is Delete, "
          "the CSI snapshot often disappears when the Backup CR is deleted. "
          "This section only sees snapshots **still present**.\n")
    snaps = oc_list(["get", "volumesnapshot", "-A"])
    if snaps is None:
        print("_could not list VolumeSnapshots._\n")
        return
    print("VolumeSnapshot count: **{0}**\n".format(len(snaps)))
    by_backup = Counter()
    rows = []
    for it in snaps:
        md = it.get("metadata") or {}
        spec = it.get("spec") or {}
        st = it.get("status") or {}
        bname = labels(md).get("velero.io/backup-name") or anns(md).get(
            "velero.io/backup-name") or "-"
        by_backup[bname] += 1
        src = (spec.get("source") or {}).get("persistentVolumeClaimName") or "-"
        rows.append([
            md.get("namespace") or "-",
            md.get("name") or "-",
            bname,
            src,
            (st or {}).get("readyToUse"),
            md.get("creationTimestamp") or "-",
        ])
    print("Snapshots grouped by `velero.io/backup-name`:\n")
    print(md_table(
        ["Count", "Backup label"],
        [[str(n), b] for b, n in by_backup.most_common()],
    ))
    print("Each snapshot:\n")
    print(md_table(
        ["NS", "VolumeSnapshot", "Backup label", "PVC", "Ready", "Created"],
        rows,
    ))

    backup_names = set()
    daily = []
    weekly = []
    if backups:
        for it in backups:
            name = (it.get("metadata") or {}).get("name") or ""
            backup_names.add(name)
            move = (it.get("spec") or {}).get("snapshotMoveData")
            if name.startswith("daily-"):
                daily.append(name)
            else:
                weekly.append(name)
    labeled = set(by_backup) - {"-"}
    print("Backups **still listed** vs snapshots **still labeled**:\n")
    print(md_table(
        ["Check", "Count / names"],
        [
            ["Backup CRs", str(len(backup_names))],
            ["Daily Backup CRs", str(len(daily))],
            ["Non-daily Backup CRs", str(len(weekly))],
            ["Snapshots with a backup label", str(sum(by_backup[b] for b in labeled))],
            ["Backup CRs with **no** leftover snapshot",
             join_list(sorted(backup_names - labeled)) or "-"],
            ["Snapshot labels with **no** Backup CR (orphans / other)",
             join_list(sorted(labeled - backup_names)) or "-"],
        ],
    ))


def section_f():
    print("## F — Restore and DataProtectionTest\n")
    restores = oc_list(["get", "restores.velero.io", "-A"])
    dpts = oc_list(["get", "dataprotectiontest", "-A"])
    print(md_table(
        ["Kind", "Count"],
        [
            ["Restore", "-" if restores is None else str(len(restores))],
            ["DataProtectionTest", "-" if dpts is None else str(len(dpts))],
        ],
    ))
    if restores:
        rows = []
        for it in restores:
            md = it.get("metadata") or {}
            st = it.get("status") or {}
            rows.append([
                md.get("namespace") or "-",
                md.get("name") or "-",
                st.get("phase") or "-",
                (it.get("spec") or {}).get("backupName") or "-",
            ])
        print(md_table(["NS", "Restore", "Phase", "Backup"], rows))
    if dpts:
        rows = []
        for it in dpts:
            md = it.get("metadata") or {}
            st = it.get("status") or {}
            rows.append([
                md.get("namespace") or "-",
                md.get("name") or "-",
                st.get("phase") or st.get("state") or "-",
            ])
        print(md_table(["NS", "DataProtectionTest", "Phase"], rows))


def main():
    print("# OpenShift OADP restore-readiness check\n")
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print("_Generated:_ {0}  ·  _Read-only (`oc get` / `oc whoami`). "
          "No Secrets. No Restore created._\n".format(stamp))
    print("> Save in a **private** notes repo. Do not commit live output "
          "next to this script.\n")
    print("> Equivalent CLI if installed: `velero get backup -n openshift-adp` "
          "is the same as `oc get backup -n openshift-adp`.\n")

    section_a()
    section_b()
    backups = section_c()
    section_d()
    section_e(backups or [])
    section_f()

    print("## Notes\n")
    print("- This script does not download Velero logs from the object store.\n")
    print("- Hook **commands** are often pod annotations, not Schedule YAML.\n")
    print("- Zero Restores means no practised restore object, not that "
          "restore is impossible.\n")


if __name__ == "__main__":
    main()
