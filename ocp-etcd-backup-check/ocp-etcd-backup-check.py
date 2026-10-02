#!/usr/bin/env python3
"""
ocp-etcd-backup-check.py — read-only report of one etcd backup CronJob.

Reads the CronJob, its script ConfigMap, retained Jobs and Pods, and
PrometheusRules that name this job. Lists the share by a read-only NFS mount
inside one short-lived debug pod, then unmounts. Does not read Pod logs.
Does not create directories, and does not run the backup script.

The debug pod is created for that listing and removed when the command
finishes. The mount uses `-o ro`. Never reads Secrets.
Requires: python3 + oc (logged in). Stdlib only.

Usage:
    python3 ocp-etcd-backup-check.py --server https://api.example:6443
    python3 ocp-etcd-backup-check.py --server https://api.example:6443 > etcd-report.md

Refuses to continue unless `oc whoami --show-server` matches --server.
Redirect stdout into a private notes repo. Do not commit live output here.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import re
import subprocess
import sys


NS_DEFAULT = "ocp-backup-etcd"
CRON_DEFAULT = "openshift-backup"
SCRIPT_KEY_DEFAULT = "backup.sh"
SECRET_NAME_RE = re.compile(r"secret|password|token|passwd|credential", re.I)
FILE_DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
LS_FILE_RE = re.compile(r"^-")
ADDR_RE = re.compile(
    r"^(?:[0-9]{1,3}(?:\.[0-9]{1,3}){3}"
    r"|[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*)$"
)
SHARE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")
NODE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


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


def oc_json(args):
    p = oc_run(args + ["-o", "json"])
    if p.returncode != 0:
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


def true_condition(status):
    true = [c for c in (status or {}).get("conditions") or [] if c.get("status") == "True"]
    for preferred in ("Complete", "Failed"):
        for cond in true:
            if cond.get("type") == preferred:
                return preferred, cond.get("reason") or ""
    if true:
        return true[0].get("type") or "", true[0].get("reason") or ""
    return "", ""


def env_rows(env_list):
    rows = []
    for item in env_list or []:
        name = item.get("name") or ""
        if SECRET_NAME_RE.search(name):
            rows.append([name, "<redacted>"])
            continue
        if "value" in item:
            rows.append([name, item.get("value")])
        elif item.get("valueFrom"):
            rows.append([name, "<valueFrom>"])
        else:
            rows.append([name, ""])
    return rows


def script_facts(text):
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    ls_at = text.find("ls -ltr")
    find_at = text.find("find ")
    order = "-"
    if ls_at >= 0 and find_at >= 0:
        order = "ls-before-find" if ls_at < find_at else "find-before-ls"
    elif ls_at >= 0:
        order = "ls-only"
    elif find_at >= 0:
        order = "find-only"
    return {
        "sha256": sha,
        "mkdir -p": text.count("mkdir -p"),
        "mkdir-p": text.count("mkdir-p"),
        "ls-find order": order,
    }


def job_rows(jobs):
    rows = []
    for job in jobs:
        meta = job.get("metadata") or {}
        status = job.get("status") or {}
        phase, reason = true_condition(status)
        owners = []
        for owner in meta.get("ownerReferences") or []:
            owners.append("{0}/{1}".format(owner.get("kind") or "", owner.get("name") or ""))
        rows.append([
            status.get("startTime") or meta.get("creationTimestamp") or "",
            meta.get("name") or "",
            phase,
            reason,
            status.get("completionTime") or "",
            ",".join(owners) or "-",
        ])
    rows.sort()
    return rows


def pod_rows(pods):
    rows = []
    for pod in pods:
        meta = pod.get("metadata") or {}
        status = pod.get("status") or {}
        rows.append([
            status.get("startTime") or meta.get("creationTimestamp") or "",
            meta.get("name") or "",
            status.get("phase") or "",
            status.get("reason") or "",
            (pod.get("spec") or {}).get("nodeName") or "",
        ])
    rows.sort()
    return rows


def env_value(env_list, name):
    for item in env_list or []:
        if item.get("name") == name and "value" in item:
            return item.get("value") or ""
    return ""


def control_nodes():
    data = oc_json(["get", "node", "-l", "node-role.kubernetes.io/master"])
    names = []
    for item in data.get("items") or []:
        name = (item.get("metadata") or {}).get("name") or ""
        if NODE_RE.match(name):
            names.append(name)
    return sorted(names)


def ls_rows(text):
    rows = []
    for line in text.splitlines():
        if not LS_FILE_RE.match(line):
            continue
        parts = line.split()
        if len(parts) < 9:
            continue
        name = parts[-1]
        size = parts[4]
        found = FILE_DATE_RE.search(name)
        rows.append([name, size, found.group(1) if found else "-"])
    return rows


def live_share(namespace, node, addr, share):
    remote = (
        "if sudo -E mount -t nfs -o ro,soft,timeo=50,retrans=2 "
        "'{addr}:/{share}' /mnt/nfs; then "
        "findmnt -n /mnt/nfs; echo '---'; "
        "ls -ltr /mnt/nfs/backup/*; rc=$?; "
        "sudo -E umount /mnt/nfs; exit $rc; "
        "else echo MOUNT_FAILED; exit 1; fi"
    ).format(addr=addr, share=share)
    p = oc_run([
        "debug", "node/{0}".format(node),
        "--to-namespace={0}".format(namespace),
        "--",
        "chroot", "/host", "sh", "-c", remote,
    ])
    text = p.stdout or ""
    err = (p.stderr or "").strip().splitlines()
    err_line = err[-1] if err else ""
    if "---" in text:
        mount_text, listing = text.split("---", 1)
    else:
        mount_text, listing = text, ""
    return {
        "node": node,
        "ok": p.returncode == 0 and bool(ls_rows(listing)),
        "returncode": p.returncode,
        "mount": " ".join(mount_text.split()),
        "listing": listing,
        "error": err_line,
    }


def rule_hits(rules, needles):
    hits = []
    kube_job = []
    for item in rules:
        meta = item.get("metadata") or {}
        ns = meta.get("namespace") or ""
        name = meta.get("name") or ""
        for group in (item.get("spec") or {}).get("groups") or []:
            for rule in group.get("rules") or []:
                alert = rule.get("alert") or ""
                expr = " ".join(str(rule.get("expr") or "").split())
                text = (alert + " " + expr).lower()
                if alert == "KubeJobFailed":
                    kube_job.append([ns, name, expr])
                if any(needle in text for needle in needles):
                    hits.append([ns, name, alert or "-", expr[:400]])
    return hits, kube_job


def main():
    parser = argparse.ArgumentParser(description="Read-only etcd backup CronJob report")
    parser.add_argument("--server", required=True, help="API server URL that oc must already be logged into")
    parser.add_argument("--namespace", default=NS_DEFAULT)
    parser.add_argument("--cronjob", default=CRON_DEFAULT)
    parser.add_argument("--script-key", default=SCRIPT_KEY_DEFAULT)
    args = parser.parse_args()

    expected = norm_server(args.server)
    who = oc_run(["whoami"])
    server = oc_run(["whoami", "--show-server"])
    if who.returncode != 0 or server.returncode != 0:
        die("oc whoami failed. Log in before running this script.")
    actual = norm_server(server.stdout)
    if actual != expected:
        die("refusing: oc server is {0}, --server is {1}".format(actual, expected))

    cron = oc_json(["get", "cronjob", args.cronjob, "-n", args.namespace])
    cm = oc_json(["get", "configmap", args.cronjob, "-n", args.namespace])
    jobs = oc_json(["get", "job", "-n", args.namespace]).get("items") or []
    pods = oc_json(["get", "pod", "-n", args.namespace]).get("items") or []
    pvcs = oc_json(["get", "pvc", "-n", args.namespace]).get("items") or []
    rules = oc_json(["get", "prometheusrule", "-A"]).get("items") or []

    spec = cron.get("spec") or {}
    job_spec = ((spec.get("jobTemplate") or {}).get("spec") or {})
    pod_spec = ((job_spec.get("template") or {}).get("spec") or {})
    containers = pod_spec.get("containers") or [{}]
    container = containers[0]
    status = cron.get("status") or {}
    script = ((cm.get("data") or {}).get(args.script_key))
    if script is None:
        die("configmap {0} has no key {1}".format(args.cronjob, args.script_key))
    facts = script_facts(script)
    addr = env_value(container.get("env"), "NFS_DEST_ADDR")
    share = env_value(container.get("env"), "NFS_SHARE")
    if not ADDR_RE.match(addr) or not SHARE_RE.match(share):
        die("NFS address or share from the CronJob is empty or has unexpected characters")

    nodes = control_nodes()
    if not nodes:
        die("no control-plane nodes found")
    live = None
    for node in nodes:
        live = live_share(args.namespace, node, addr, share)
        if live["ok"]:
            break
    files = ls_rows(live["listing"]) if live else []
    dates = []
    for row in files:
        if row[2] != "-" and row[2] not in dates:
            dates.append(row[2])

    hits, kube_job = rule_hits(rules, [args.cronjob.lower(), args.namespace.lower()])

    print("# etcd backup check\n")
    print("File names below are from a read-only mount of the share. The debug pod is removed when the command finishes.\n")
    print(md_table(["Item", "Value"], [
        ["user", (who.stdout or "").strip()],
        ["api", actual],
        ["namespace", args.namespace],
        ["cronjob", args.cronjob],
        ["schedule", spec.get("schedule") or ""],
        ["suspend", spec.get("suspend")],
        ["successfulJobsHistoryLimit", spec.get("successfulJobsHistoryLimit")],
        ["failedJobsHistoryLimit", spec.get("failedJobsHistoryLimit")],
        ["activeDeadlineSeconds", pod_spec.get("activeDeadlineSeconds")],
        ["lastScheduleTime", status.get("lastScheduleTime") or ""],
        ["lastSuccessfulTime", status.get("lastSuccessfulTime") or ""],
        ["script sha256", facts["sha256"]],
        ["mkdir -p count", facts["mkdir -p"]],
        ["mkdir-p count", facts["mkdir-p"]],
        ["ls/find in script", facts["ls-find order"]],
        ["pvc count", len(pvcs)],
        ["share node", (live or {}).get("node") or ""],
        ["share mount", (live or {}).get("mount") or ""],
        ["share list error", "" if (live or {}).get("ok") else (live or {}).get("error") or ""],
        ["dates on share", ", ".join(dates) or ""],
        ["rules naming this job", len(hits)],
    ]))

    print("\n## Env\n")
    print(md_table(["Name", "Value"], env_rows(container.get("env"))))

    print("\n## Jobs\n")
    print(md_table(["Start", "Name", "Phase", "Reason", "Completed", "Owner"], job_rows(jobs)))

    print("\n## Pods\n")
    print(md_table(["Start", "Name", "Phase", "Reason", "Node"], pod_rows(pods)))

    print("\n## Share listing\n")
    print(md_table(["File", "Bytes", "Date in name"], files))

    print("\n## PrometheusRules naming this CronJob or namespace\n")
    print(md_table(["Namespace", "Rule", "Alert", "Expr"], hits))

    print("\n## KubeJobFailed\n")
    print(md_table(["Namespace", "Rule", "Expr"], kube_job))


if __name__ == "__main__":
    main()
