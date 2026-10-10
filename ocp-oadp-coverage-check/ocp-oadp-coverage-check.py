#!/usr/bin/env python3
"""
ocp-oadp-coverage-check.py — read-only report of which namespaces OADP
Schedules cover, and which VM namespaces no active Schedule covers.

Sections:
  1. Schedules: cron, paused, included / excluded namespaces, label selectors
  2. Namespaces in an OADP Schedule: active and paused Schedules per namespace
  3. VM namespaces not in any active Schedule, with the reason

Coverage rules (same as Velero):
  - includedNamespaces empty or "*" means all namespaces
  - includedNamespaces / excludedNamespaces entries may be globs ("app-*")
  - excludedNamespaces wins over includedNamespaces
  - a paused Schedule does not count as coverage; it is shown separately
  - a Schedule with a label selector may skip some VMs; it counts as
    coverage but is flagged for a manual check

Uses `oc get` and `oc whoami` only. Never reads Secrets.
Requires: python3 + oc (logged in). Stdlib only.

Usage:
    python3 ocp-oadp-coverage-check.py --server https://api.example:6443 > coverage.md

Refuses to continue unless `oc whoami --show-server` matches --server.
Redirect stdout into a private notes repo. Do not commit live output here.
"""

from __future__ import print_function

import argparse
import fnmatch
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime


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


def kind_missing(err):
    return "doesn't have a resource type" in (err or "").lower()


def oc_items(args):
    """Return the items list. [] if the kind does not exist. Exit on other errors."""
    p = oc_run(args + ["-o", "json"])
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()
        if kind_missing(err):
            return []
        lines = err.splitlines()
        die("oc {0} failed: {1}".format(" ".join(args), lines[-1] if lines else p.returncode))
    try:
        return (json.loads(p.stdout) or {}).get("items") or []
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


def join_list(value):
    return ", ".join(str(x) for x in value) if value else "-"


def matches(ns, patterns):
    return any(p == "*" or fnmatch.fnmatchcase(ns, p) for p in patterns)


def is_glob(p):
    return any(c in p for c in "*?[")


class Schedule(object):
    def __init__(self, item):
        md = item.get("metadata") or {}
        spec = item.get("spec") or {}
        tmpl = spec.get("template") or {}
        self.namespace = md.get("namespace") or "-"
        self.name = md.get("name") or "-"
        self.cron = spec.get("schedule") or "-"
        self.paused = bool(spec.get("paused"))
        self.included = tmpl.get("includedNamespaces") or []
        self.excluded = tmpl.get("excludedNamespaces") or []
        self.selector = bool(tmpl.get("labelSelector") or tmpl.get("orLabelSelectors"))
        self.last_backup = (item.get("status") or {}).get("lastBackup") or "-"

    @property
    def all_namespaces(self):
        return not self.included or "*" in self.included

    def covers(self, ns):
        """Return 'yes', 'excluded', or 'no'."""
        if not (self.all_namespaces or matches(ns, self.included)):
            return "no"
        if matches(ns, self.excluded):
            return "excluded"
        return "yes"


def main():
    parser = argparse.ArgumentParser(description="Read-only OADP Schedule vs VM namespace coverage")
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

    schedules = sorted(
        (Schedule(it) for it in oc_items(["get", "schedules.velero.io", "-A"])),
        key=lambda s: (s.namespace, s.name),
    )
    vms = oc_items(["get", "virtualmachines.kubevirt.io", "-A"])
    vm_count = Counter((it.get("metadata") or {}).get("namespace") or "-" for it in vms)
    all_ns = sorted(
        (it.get("metadata") or {}).get("name")
        for it in oc_items(["get", "namespaces"])
    )

    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print("# OADP coverage check\n")
    print("_Server:_ `{0}`  ·  _Generated:_ {1}  ·  _Read-only (`oc get` / `oc whoami`)._\n"
          .format(actual, stamp))
    print("> Save this file in a **private** notes repo. Do not commit live "
          "output next to this script.\n")
    print("Schedules: **{0}** ({1} paused)  ·  VMs: **{2}** in **{3}** namespaces\n".format(
        len(schedules), sum(1 for s in schedules if s.paused), len(vms), len(vm_count)))

    # 1. Schedules
    print("## 1. Schedules\n")
    print(md_table(
        ["Namespace", "Name", "Cron", "Paused", "Included namespaces",
         "Excluded namespaces", "Label selector", "Last backup"],
        [[s.namespace, s.name, s.cron, "yes" if s.paused else "no",
          "ALL" if s.all_namespaces else join_list(s.included),
          join_list(s.excluded), "yes" if s.selector else "no", s.last_backup]
         for s in schedules],
    ))

    flags = []
    for s in schedules:
        if s.all_namespaces:
            flags.append("`{0}` covers **all** namespaces (included is empty or `*`).".format(s.name))
        globs = [p for p in s.included + s.excluded if p != "*" and is_glob(p)]
        if globs:
            flags.append("`{0}` uses glob patterns: {1}.".format(s.name, join_list(globs)))
        if s.selector:
            flags.append("`{0}` has a label selector. Only matching objects are backed up; "
                         "check VMs in its namespaces by hand.".format(s.name))
        missing = [p for p in s.included if not is_glob(p) and p not in all_ns]
        if missing:
            flags.append("`{0}` lists namespaces that do not exist: {1}.".format(s.name, join_list(missing)))
    if flags:
        print("**Flags**\n")
        for f in flags:
            print("- " + f)
        print()

    # 2. Namespaces in an OADP Schedule
    print("## 2. Namespaces in an OADP Schedule\n")
    rows = []
    for ns in all_ns:
        active = [s.name for s in schedules if not s.paused and s.covers(ns) == "yes"]
        paused = [s.name for s in schedules if s.paused and s.covers(ns) == "yes"]
        if active or paused:
            rows.append([ns, join_list(active), join_list(paused), vm_count.get(ns, 0)])
    print("Namespaces that exist on the cluster and are covered by at least one Schedule.\n")
    print(md_table(["Namespace", "Active schedules", "Paused schedules", "VMs"], rows))

    # 3. VM namespaces not in any active Schedule
    print("## 3. VM namespaces not in any active Schedule\n")
    rows = []
    for ns in sorted(vm_count):
        results = [(s, s.covers(ns)) for s in schedules]
        if any(r == "yes" and not s.paused for s, r in results):
            continue
        paused = [s.name for s, r in results if r == "yes" and s.paused]
        excluded = [s.name for s, r in results if r == "excluded"]
        if paused:
            reason = "only in paused schedule: " + join_list(paused)
        elif excluded:
            reason = "excluded by: " + join_list(excluded)
        else:
            reason = "not listed in any schedule"
        rows.append([ns, vm_count[ns], reason])
    if not vms:
        print("_no VirtualMachines on this cluster_\n")
    else:
        print(md_table(["Namespace", "VMs", "Reason"], rows))

    print("## Notes\n")
    print("- \"In a Schedule\" means the namespace is selected. It does not mean the "
          "last backup Completed, or that a restore was tested.")
    print("- Paused schedules do not count as coverage.")
    print("- Secrets are never read.")


if __name__ == "__main__":
    main()
