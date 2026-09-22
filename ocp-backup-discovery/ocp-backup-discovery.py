#!/usr/bin/env python3
"""
ocp-backup-discovery.py — read-only inventory of OpenShift OADP / Velero.

Purpose: same first-pass picture on every cluster (operator, DPA, BSL,
schedules, backup phases, CSI classes, VM coverage, backup alerts)
before a deeper report.

etcd / AAP-native / VolSync: presence only.

Read-only. Runs `oc get` / `oc whoami` only. Never reads Secrets.
Requires: python3 + oc (logged in). Stdlib only.

Usage:
    python3 ocp-backup-discovery.py
    python3 ocp-backup-discovery.py > inventory.md

This script is generic (safe for public repos). Redirect stdout that contains
cluster identity into a **private** notes repo. Do not commit live output here.
"""

from __future__ import print_function

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime


URL_OR_IP_RE = re.compile(
    r"https?://|\b\d{1,3}(?:\.\d{1,3}){3}\b",
    re.I,
)

BACKUP_ALERT_RE = re.compile(r"backup|oadp|velero|partial", re.I)

ETCD_NS_RE = re.compile(r"etcd", re.I)
AAP_NS_RE = re.compile(r"(^|-)aap($|-)", re.I)
BACKUP_CRON_RE = re.compile(r"backup", re.I)


def oc_run(args, check=True):
    return subprocess.run(
        ["oc"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=check,
    )


def oc_json(args):
    try:
        out = oc_run(args + ["-o", "json"], check=True)
        return json.loads(out.stdout)
    except (subprocess.CalledProcessError, ValueError) as e:
        err = ""
        if isinstance(e, subprocess.CalledProcessError):
            err = (e.stderr or "").strip().splitlines()
            err = err[-1] if err else str(e)
        print("  > failed: oc {0} -o json".format(" ".join(args)), file=sys.stderr)
        if err:
            print("  > {0}".format(err), file=sys.stderr)
        return None


def oc_text(args):
    try:
        return oc_run(args, check=False).stdout.strip()
    except Exception:
        return ""


def oc_ok_table(args):
    p = oc_run(args, check=False)
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip().splitlines()
        return err[-1] if err else "get-failed"
    return (p.stdout or "").rstrip() or "(empty)"


def kind_missing(err):
    e = (err or "").lower()
    return "doesn't have a resource type" in e or "not found" in e


def oc_list(args):
    """Return items list, or None if kind missing / get failed."""
    p = oc_run(args + ["-o", "json"], check=False)
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
    r = ["| " + " | ".join(str(c) if c not in (None, "") else "-" for c in row) + " |"
         for row in rows]
    return "\n".join([h, s] + r) + "\n"


def jsonpath_first(data, *keys, default="-"):
    cur = data
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    if cur is None or cur == "":
        return default
    return str(cur)


def redact_value(value):
    if value is None or value == "":
        return "-"
    s = str(value)
    if URL_OR_IP_RE.search(s):
        return "<redacted>"
    return s


def join_list(value):
    if not value:
        return "-"
    if isinstance(value, list):
        return ", ".join(str(x) for x in value) or "-"
    return str(value)


def section_a():
    print("## A — identity\n")
    who = oc_text(["whoami"]) or "(whoami failed)"
    server = oc_text(["whoami", "--show-server"]) or "-"
    cv = oc_json(["get", "clusterversion", "version"]) or {}
    st = cv.get("status") or {}
    desired = jsonpath_first(st, "desired", "version")
    print(md_table(
        ["Item", "Value"],
        [
            ["user", who],
            ["api", server],
            ["OCP version", desired],
            ["channel", jsonpath_first(cv, "spec", "channel")],
        ],
    ))


def section_b():
    print("## B — OADP / Velero\n")
    dpas = oc_list(["get", "dpa", "-A"])
    if dpas is None:
        print("_could not list DataProtectionApplications._\n")
        return []

    if not dpas:
        print("_No DataProtectionApplication found._\n")
        print("```")
        print(oc_ok_table(["get", "csv", "-A"]))
        print("```\n")
        return []

    rows = []
    dpa_ns = []
    for it in dpas:
        md = it.get("metadata") or {}
        spec = it.get("spec") or {}
        cfg = spec.get("configuration") or {}
        velero = cfg.get("velero") or {}
        node = cfg.get("nodeAgent") or {}
        st = it.get("status") or {}
        ns = md.get("namespace") or "-"
        dpa_ns.append(ns)
        rows.append([
            ns,
            md.get("name") or "-",
            st.get("phase") or join_list([
                c.get("type") for c in (st.get("conditions") or [])
                if c.get("status") == "True"
            ]),
            join_list(velero.get("defaultPlugins")),
            join_list(velero.get("featureFlags")),
            velero.get("defaultSnapshotMoveData"),
            node.get("enable"),
            node.get("uploaderType") or "-",
        ])
    print("DataProtectionApplication:\n")
    print(md_table(
        ["Namespace", "Name", "Status", "Plugins", "Feature flags",
         "defaultSnapshotMoveData", "nodeAgent", "uploader"],
        rows,
    ))

    for ns in sorted(set(dpa_ns)):
        print("OADP-related CSV in `{0}`:\n".format(ns))
        csvs = oc_list(["get", "csv", "-n", ns]) or []
        csv_rows = []
        for c in csvs:
            cmd = c.get("metadata") or {}
            cname = cmd.get("name") or ""
            if not re.search(r"oadp|velero", cname, re.I):
                continue
            cst = c.get("status") or {}
            csv_rows.append([
                cname,
                jsonpath_first(c, "spec", "displayName"),
                jsonpath_first(c, "spec", "version"),
                cst.get("phase") or "-",
            ])
        print(md_table(["CSV", "Display", "Version", "Phase"], csv_rows))
        print("Deploy / daemonset in `{0}`:\n".format(ns))
        print("```")
        print(oc_ok_table(["get", "deploy,ds", "-n", ns]))
        print("```\n")

    return list(set(dpa_ns))


def section_c(dpa_namespaces):
    print("## C — storage locations\n")
    print("BackupStorageLocation (S3 URL / IP values redacted):\n")
    bsls = oc_list(["get", "backupstoragelocation", "-A"])
    rows = []
    if bsls:
        for it in bsls:
            md = it.get("metadata") or {}
            spec = it.get("spec") or {}
            st = it.get("status") or {}
            obj = spec.get("objectStorage") or {}
            cfg = spec.get("config") or {}
            safe_cfg = []
            for k in sorted(cfg):
                if re.search(r"secret|token|password|key", k, re.I):
                    safe_cfg.append("{0}=<redacted>".format(k))
                else:
                    safe_cfg.append("{0}={1}".format(k, redact_value(cfg[k])))
            cred = spec.get("credential") or {}
            rows.append([
                md.get("namespace") or "-",
                md.get("name") or "-",
                spec.get("provider") or "-",
                obj.get("bucket") or "-",
                obj.get("prefix") or "-",
                st.get("phase") or "-",
                spec.get("default"),
                "yes" if cred else "no",
                "; ".join(safe_cfg) or "-",
            ])
    print(md_table(
        ["Namespace", "Name", "Provider", "Bucket", "Prefix", "Phase",
         "Default", "Credential ref", "Config (redacted)"],
        rows,
    ))

    print("VolumeSnapshotLocation:\n")
    print("```")
    print(oc_ok_table(["get", "volumesnapshotlocation", "-A"]))
    print("```\n")


def section_d():
    print("## D — schedules\n")
    items = oc_list(["get", "schedule.velero.io", "-A"])
    rows = []
    included = []
    if items:
        for it in items:
            md = it.get("metadata") or {}
            spec = it.get("spec") or {}
            tmpl = spec.get("template") or {}
            st = it.get("status") or {}
            ns_list = tmpl.get("includedNamespaces") or []
            included.extend(ns_list)
            rows.append([
                md.get("namespace") or "-",
                md.get("name") or "-",
                spec.get("schedule") or "-",
                tmpl.get("ttl") or "-",
                join_list(ns_list),
                tmpl.get("snapshotMoveData"),
                tmpl.get("defaultVolumesToFsBackup"),
                tmpl.get("storageLocation") or "-",
                spec.get("paused"),
                st.get("lastBackup") or "-",
                st.get("phase") or "-",
            ])
    print(md_table(
        ["Namespace", "Name", "Cron", "TTL", "Included namespaces",
         "snapshotMoveData", "fsBackup", "BSL", "Paused", "Last backup",
         "Phase"],
        rows,
    ))
    return sorted(set(included))


def section_e():
    print("## E — backups\n")
    items = oc_list(["get", "backups.velero.io", "-A"])
    if items is None:
        print("_could not list Backups._\n")
        return
    phases = Counter((it.get("status") or {}).get("phase") or "Unknown"
                     for it in items)
    print("Count: **{0}**\n".format(len(items)))
    print("By phase:\n")
    print(md_table(
        ["Phase", "Count"],
        [[p, str(n)] for p, n in phases.most_common()],
    ))
    rows = []
    for it in items:
        md = it.get("metadata") or {}
        spec = it.get("spec") or {}
        st = it.get("status") or {}
        hooks = st.get("hookStatus") or {}
        rows.append([
            md.get("namespace") or "-",
            md.get("name") or "-",
            st.get("phase") or "-",
            st.get("errors") if st.get("errors") is not None else "-",
            st.get("warnings") if st.get("warnings") is not None else "-",
            "{0}/{1}".format(
                hooks.get("hooksFailed") if hooks.get("hooksFailed") is not None else 0,
                hooks.get("hooksAttempted") if hooks.get("hooksAttempted") is not None else 0,
            ),
            st.get("csiVolumeSnapshotsCompleted"),
            st.get("csiVolumeSnapshotsAttempted"),
            spec.get("snapshotMoveData"),
            spec.get("defaultVolumesToFsBackup"),
            st.get("startTimestamp") or "-",
            st.get("completionTimestamp") or "-",
        ])
    rows.sort(key=lambda r: r[10], reverse=True)
    print("Each Backup:\n")
    print(md_table(
        ["Namespace", "Name", "Phase", "Errors", "Warn", "Hooks fail/try",
         "CSI done", "CSI try", "Move data", "fsBackup", "Start", "End"],
        rows,
    ))


def section_f():
    print("## F — restores\n")
    items = oc_list(["get", "restores.velero.io", "-A"])
    if items is None:
        print("_could not list Restores._\n")
        return
    print("Count: **{0}**\n".format(len(items)))
    if not items:
        return
    phases = Counter((it.get("status") or {}).get("phase") or "Unknown"
                     for it in items)
    print(md_table(
        ["Phase", "Count"],
        [[p, str(n)] for p, n in phases.most_common()],
    ))
    rows = []
    for it in items:
        md = it.get("metadata") or {}
        st = it.get("status") or {}
        rows.append([
            md.get("namespace") or "-",
            md.get("name") or "-",
            st.get("phase") or "-",
            md.get("creationTimestamp") or "-",
        ])
    print(md_table(["Namespace", "Name", "Phase", "Created"], rows))


def section_g():
    print("## G — CSI / storage\n")
    print("StorageClass:\n")
    print("```")
    print(oc_ok_table(["get", "sc"]))
    print("```\n")
    print("VolumeSnapshotClass:\n")
    print("```")
    print(oc_ok_table(["get", "volumesnapshotclass"]))
    print("```\n")
    snaps = oc_list(["get", "volumesnapshot", "-A"])
    if snaps is None:
        print("_could not list VolumeSnapshots._\n")
        return
    print("VolumeSnapshot count: **{0}**\n".format(len(snaps)))
    by_ns = Counter(
        (it.get("metadata") or {}).get("namespace") or "-"
        for it in snaps
    )
    print(md_table(
        ["Count", "Namespace"],
        [[str(n), ns] for ns, n in by_ns.most_common()],
    ))


def section_h(scheduled_ns):
    print("## H — VMs vs schedule coverage\n")
    vms = oc_list(["get", "vm", "-A"])
    if vms is None:
        print("_could not list VirtualMachines (kind missing or get failed)._\n")
        return
    print("VirtualMachine count: **{0}**\n".format(len(vms)))
    by_ns = Counter(
        (it.get("metadata") or {}).get("namespace") or "-"
        for it in vms
    )
    sched = set(scheduled_ns or [])
    rows = []
    for ns, n in sorted(by_ns.items()):
        rows.append([ns, str(n), "yes" if ns in sched else "NO"])
    print(md_table(["VM namespace", "VMs", "In an OADP Schedule"], rows))
    extra = sorted(sched - set(by_ns))
    if extra:
        print("Scheduled namespaces with **no** VMs (containers or empty):\n")
        print(md_table(["Namespace"], [[x] for x in extra]))


def section_i():
    print("## I — backup-related alerts\n")
    print("Read-only `oc get prometheusrule`. Does **not** query Prometheus for "
          "firing alerts. Classifies rule expressions only.\n")
    items = oc_list(["get", "prometheusrule", "-A"])
    if items is None:
        print("_could not list PrometheusRules._\n")
        return
    rows = []
    full = []
    partial = []
    for it in items:
        md = it.get("metadata") or {}
        name = md.get("name") or ""
        ns = md.get("namespace") or "-"
        for group in (it.get("spec") or {}).get("groups") or []:
            for rule in group.get("rules") or []:
                alert = rule.get("alert") or ""
                expr = rule.get("expr") or ""
                blob = " ".join([name, alert, expr])
                if not BACKUP_ALERT_RE.search(blob):
                    continue
                rows.append([ns, name, alert or "(recording)", expr or "-"])
                label = "{0}/{1} {2}".format(ns, name, alert or "(recording)")
                if "velero_backup_failure_total" in expr:
                    full.append(label)
                if "velero_backup_partial_failure_total" in expr:
                    partial.append(label)
    print(md_table(
        ["Check", "Present"],
        [
            ["Full failure rule (`velero_backup_failure_total`)",
             ", ".join(full) if full else "NO"],
            ["Partial failure rule (`velero_backup_partial_failure_total`)",
             ", ".join(partial) if partial else "NO"],
        ],
    ))
    print("Matching PrometheusRules:\n")
    print(md_table(["Namespace", "PrometheusRule", "Alert", "Expr"], rows))


def section_j():
    print("## J — parked (presence only)\n")
    print("Not OADP. Listed so other clusters can be compared later.\n")

    cron = oc_list(["get", "cronjob", "-A"]) or []
    etcd_rows = []
    aap_rows = []
    for it in cron:
        md = it.get("metadata") or {}
        ns = md.get("namespace") or ""
        name = md.get("name") or ""
        spec = it.get("spec") or {}
        if ETCD_NS_RE.search(ns) and BACKUP_CRON_RE.search(name + ns):
            etcd_rows.append([ns, name, spec.get("schedule") or "-", spec.get("suspend")])
        if AAP_NS_RE.search(ns) and BACKUP_CRON_RE.search(name):
            aap_rows.append([ns, name, spec.get("schedule") or "-", spec.get("suspend")])

    print("etcd-ish backup CronJobs:\n")
    print(md_table(["Namespace", "Name", "Schedule", "Suspend"], etcd_rows))
    print("AAP-ish backup CronJobs:\n")
    print(md_table(["Namespace", "Name", "Schedule", "Suspend"], aap_rows))

    print("VolSync CRs (operator may exist with zero CRs):\n")
    src = oc_list(["get", "replicationsource", "-A"])
    dst = oc_list(["get", "replicationdestination", "-A"])
    print(md_table(
        ["Kind", "Count"],
        [
            ["ReplicationSource", "-" if src is None else str(len(src))],
            ["ReplicationDestination", "-" if dst is None else str(len(dst))],
        ],
    ))


def main():
    print("# OpenShift OADP backup discovery\n")
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print("_Generated:_ {0}  ·  _Read-only (`oc get` / `oc whoami`). "
          "No Secrets. BSL endpoints redacted._\n".format(stamp))
    print("> Save this file in a **private** notes repo. Do not commit live "
          "output next to this script.\n")

    section_a()
    dpa_ns = section_b()
    section_c(dpa_ns)
    scheduled_ns = section_d()
    section_e()
    section_f()
    section_g()
    section_h(scheduled_ns)
    section_i()
    section_j()

    print("## Notes\n")
    print("- OADP is the focus. etcd / AAP-native / VolSync are presence only.\n")
    print("- Daily vs weekly is in Schedule TTL and `snapshotMoveData`, "
          "not in the script logic.\n")
    print("- Secrets (BSL credentials, hook env) are never read.\n")


if __name__ == "__main__":
    main()
