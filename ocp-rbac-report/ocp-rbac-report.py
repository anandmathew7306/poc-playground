#!/usr/bin/env python3
"""
ocp-rbac-report.py — generate an RBAC reference report for an OpenShift cluster.

Full scrape (default):
  - Summary counts
  - Elevated focus (cluster-admin / admin / customizable)
  - All ClusterRoleBindings
  - All RoleBindings (namespaced)
  - ClusterRoles inventory (compact)
  - Subject rollups (Users / Groups / ServiceAccounts in CRBs)

Call-ready subset:
  python3 ocp-rbac-report.py --focus elevated

Read-only. Runs `oc get ... -o json` and prints markdown tables.
Requires: python3 + oc (logged in). No pip packages.

Usage:
    python3 ocp-rbac-report.py
    python3 ocp-rbac-report.py --focus elevated
    python3 ocp-rbac-report.py --elevated-roles cluster-admin,admin,edit
    python3 ocp-rbac-report.py > rbac-<env>-<domain>-<site>.report.md

Save live output (cluster identity, user names) into a **private** notes repo.
This directory is safe for public repos (generic script only).
"""

from __future__ import print_function

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime

# Default roles treated as "elevated" for the focus section / call narrative.
DEFAULT_ELEVATED = (
    "cluster-admin",
    "admin",
    "system:admin",
)


def oc_json(args):
    """Run `oc <args> -o json` and return parsed JSON (or None on failure)."""
    cmd = ["oc"] + args + ["-o", "json"]
    try:
        out = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
        return json.loads(out.stdout)
    except subprocess.CalledProcessError as e:
        print("  > command failed: {}".format(" ".join(cmd)), file=sys.stderr)
        err = (e.stderr or "").strip()
        if err:
            print("  > {}".format(err.splitlines()[-1]), file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print("  > could not parse JSON: {}".format(" ".join(cmd)), file=sys.stderr)
        return None


def oc_text(args):
    try:
        return subprocess.run(
            ["oc"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        ).stdout.strip()
    except Exception:
        return ""


def md_table(headers, rows):
    if not rows:
        return "_no data_\n"
    h = "| " + " | ".join(headers) + " |"
    s = "|" + "|".join(["---"] * len(headers)) + "|"
    r = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([h, s] + r) + "\n"


def role_ref_name(item):
    ref = item.get("roleRef") or {}
    return ref.get("name") or "-", ref.get("kind") or "-", ref.get("apiGroup") or "-"


def fmt_subjects(subjects):
    """Compact subject list for a table cell."""
    if not subjects:
        return "(none)"
    parts = []
    for s in subjects:
        kind = s.get("kind") or "?"
        name = s.get("name") or "?"
        ns = s.get("namespace")
        if kind == "ServiceAccount" and ns:
            parts.append("SA:{}/{}".format(ns, name))
        elif kind == "Group":
            parts.append("Group:{}".format(name))
        elif kind == "User":
            parts.append("User:{}".format(name))
        else:
            parts.append("{}:{}".format(kind, name))
    return ", ".join(parts)


def subject_key(s):
    kind = s.get("kind") or "?"
    name = s.get("name") or "?"
    ns = s.get("namespace") or ""
    if kind == "ServiceAccount":
        return (kind, ns, name)
    return (kind, "", name)


def subject_label(key):
    kind, ns, name = key
    if kind == "ServiceAccount":
        return "SA:{}/{}".format(ns, name)
    return "{}:{}".format(kind, name)


def is_wildcard_admin(cr):
    """Heuristic: ClusterRole grants * on * (or all resources) — treat as elevated."""
    for rule in cr.get("rules") or []:
        verbs = set(rule.get("verbs") or [])
        resources = set(rule.get("resources") or [])
        api_groups = set(rule.get("apiGroups") or [])
        if "*" in verbs and ("*" in resources or resources == {"*"}):
            if not api_groups or "*" in api_groups:
                return True
    return False


def compact_rules(cr, limit=3):
    """Short rule summary for ClusterRole inventory."""
    rules = cr.get("rules") or []
    if not rules:
        if cr.get("aggregationRule"):
            return "(aggregated)"
        return "(no rules)"
    bits = []
    for rule in rules[:limit]:
        verbs = ",".join(rule.get("verbs") or []) or "-"
        res = ",".join(rule.get("resources") or []) or "-"
        bits.append("{} on {}".format(verbs, res))
    extra = len(rules) - limit
    if extra > 0:
        bits.append("+{} more".format(extra))
    return "; ".join(bits)


def load_rbac():
    """Fetch all RBAC objects once."""
    data = {
        "clusterroles": oc_json(["get", "clusterroles"]),
        "clusterrolebindings": oc_json(["get", "clusterrolebindings"]),
        "roles": oc_json(["get", "roles", "-A"]),
        "rolebindings": oc_json(["get", "rolebindings", "-A"]),
    }
    return data


def section_summary(data):
    cr = data["clusterroles"]
    crb = data["clusterrolebindings"]
    roles = data["roles"]
    rb = data["rolebindings"]
    rows = [
        ["ClusterRoles", len((cr or {}).get("items") or []) if cr else "get-failed"],
        ["ClusterRoleBindings",
         len((crb or {}).get("items") or []) if crb else "get-failed"],
        ["Roles (namespaced)",
         len((roles or {}).get("items") or []) if roles else "get-failed"],
        ["RoleBindings (namespaced)",
         len((rb or {}).get("items") or []) if rb else "get-failed"],
    ]
    return ("## Summary counts\n\n" + md_table(["Kind", "Count"], rows))


def elevated_role_names(data, configured):
    """Configured names plus ClusterRoles that look like wildcard admins."""
    names = set(configured)
    cr = data.get("clusterroles")
    if cr:
        for item in cr.get("items") or []:
            name = (item.get("metadata") or {}).get("name") or ""
            if name and is_wildcard_admin(item):
                names.add(name)
    return names


def section_elevated(data, elevated_names):
    crb = data.get("clusterrolebindings")
    if not crb:
        return ("## Elevated focus\n\n"
                "_could not retrieve ClusterRoleBindings_\n")

    elev = sorted(elevated_names)
    rows = []
    subject_hits = Counter()
    by_role = Counter()

    for item in crb.get("items") or []:
        meta = item.get("metadata") or {}
        rname, rkind, _ = role_ref_name(item)
        if rkind not in ("ClusterRole", "-") and rkind != "ClusterRole":
            # RoleRef kind should be ClusterRole for CRBs
            pass
        if rname not in elevated_names:
            continue
        by_role[rname] += 1
        subjects = item.get("subjects") or []
        for s in subjects:
            subject_hits[subject_key(s)] += 1
        rows.append([
            meta.get("name", ""),
            rname,
            fmt_subjects(subjects),
        ])

    rows.sort(key=lambda r: (r[1], r[0]))

    rollup_rows = [
        [subject_label(k), n]
        for k, n in sorted(subject_hits.items(), key=lambda x: (-x[1], x[0]))
    ]
    role_rows = [[role, n] for role, n in sorted(by_role.items(), key=lambda x: (-x[1], x[0]))]

    out = []
    out.append("## Elevated focus\n")
    out.append(
        "_ClusterRoleBindings whose `roleRef.name` is in the elevated set "
        "(configured defaults plus wildcard `*/*` ClusterRoles detected)._\n"
    )
    out.append("_Elevated role names:_ `{}`\n".format("`, `".join(elev) if elev else "(none)"))
    out.append("\n### Elevated bindings by role\n\n")
    out.append(md_table(["ClusterRole", "CRB count"], role_rows))
    out.append("\n### Elevated subjects (rollup)\n\n")
    out.append(
        "_How many elevated CRBs each subject appears in "
        "(same subject can appear in multiple bindings)._\n\n"
    )
    out.append(md_table(["Subject", "Elevated CRB hits"], rollup_rows))
    out.append("\n### Elevated ClusterRoleBindings\n\n")
    out.append(md_table(["Binding", "ClusterRole", "Subjects"], rows))
    return "".join(out)


def section_clusterrolebindings(data):
    crb = data.get("clusterrolebindings")
    if not crb:
        return ("## ClusterRoleBindings\n\n"
                "_could not retrieve_\n")
    rows = []
    for item in crb.get("items") or []:
        meta = item.get("metadata") or {}
        rname, rkind, _ = role_ref_name(item)
        rows.append([
            meta.get("name", ""),
            rkind,
            rname,
            fmt_subjects(item.get("subjects") or []),
        ])
    rows.sort(key=lambda r: r[0])
    return ("## ClusterRoleBindings\n\n"
            "_All cluster-scoped role bindings._\n\n"
            + md_table(["Binding", "roleRef.kind", "roleRef.name", "Subjects"], rows))


def section_rolebindings(data):
    rb = data.get("rolebindings")
    if not rb:
        return ("## RoleBindings\n\n"
                "_could not retrieve_\n")
    rows = []
    for item in rb.get("items") or []:
        meta = item.get("metadata") or {}
        rname, rkind, _ = role_ref_name(item)
        rows.append([
            meta.get("namespace", ""),
            meta.get("name", ""),
            rkind,
            rname,
            fmt_subjects(item.get("subjects") or []),
        ])
    rows.sort(key=lambda r: (r[0], r[1]))
    return ("## RoleBindings (namespaced)\n\n"
            "_All namespace RoleBindings. Large on busy clusters._\n\n"
            + md_table(
                ["Namespace", "Binding", "roleRef.kind", "roleRef.name", "Subjects"],
                rows,
            ))


def section_clusterroles(data):
    cr = data.get("clusterroles")
    if not cr:
        return ("## ClusterRoles\n\n"
                "_could not retrieve_\n")
    rows = []
    for item in cr.get("items") or []:
        meta = item.get("metadata") or {}
        name = meta.get("name", "")
        agg = "yes" if item.get("aggregationRule") else ""
        wild = "yes" if is_wildcard_admin(item) else ""
        nrules = len(item.get("rules") or [])
        rows.append([
            name,
            agg or "-",
            wild or "-",
            str(nrules),
            compact_rules(item),
        ])
    rows.sort(key=lambda r: r[0])
    return ("## ClusterRoles (inventory)\n\n"
            "_Compact inventory — not a full rule dump. "
            "`wildcard` = verbs/resources look like cluster-admin-class._\n\n"
            + md_table(
                ["Name", "aggregated", "wildcard", "#rules", "rules (sample)"],
                rows,
            ))


def section_roles(data):
    roles = data.get("roles")
    if not roles:
        return ("## Roles (namespaced)\n\n"
                "_could not retrieve_\n")
    # Count-only by namespace to avoid enormous dumps; list names if modest.
    by_ns = defaultdict(list)
    for item in roles.get("items") or []:
        meta = item.get("metadata") or {}
        by_ns[meta.get("namespace") or ""].append(meta.get("name") or "")
    rows = []
    for ns in sorted(by_ns):
        names = sorted(by_ns[ns])
        sample = ", ".join(names[:8])
        if len(names) > 8:
            sample += ", +{} more".format(len(names) - 8)
        rows.append([ns, str(len(names)), sample])
    return ("## Roles (namespaced)\n\n"
            "_Per-namespace counts + name sample (full Role rule dump omitted)._\n\n"
            + md_table(["Namespace", "#Roles", "Names (sample)"], rows))


def section_crb_subjects(data):
    crb = data.get("clusterrolebindings")
    if not crb:
        return ("## ClusterRoleBinding subjects (rollup)\n\n"
                "_could not retrieve_\n")
    by_kind = Counter()
    subjects = Counter()
    for item in crb.get("items") or []:
        for s in item.get("subjects") or []:
            by_kind[s.get("kind") or "?"] += 1
            subjects[subject_key(s)] += 1
    kind_rows = [[k, n] for k, n in sorted(by_kind.items(), key=lambda x: (-x[1], x[0]))]
    # Cap subject list noise — top by hit count then alpha
    sub_rows = [
        [subject_label(k), n]
        for k, n in sorted(subjects.items(), key=lambda x: (-x[1], x[0]))
    ]
    return (
        "## ClusterRoleBinding subjects (rollup)\n\n"
        "### By subject kind\n\n"
        + md_table(["Kind", "Appearances in CRB subjects"], kind_rows)
        + "\n### All subjects\n\n"
        + md_table(["Subject", "CRB appearances"], sub_rows)
    )


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="OpenShift RBAC reference report (read-only oc get).",
    )
    p.add_argument(
        "--focus",
        choices=("full", "elevated"),
        default="full",
        help="full = entire RBAC scrape; elevated = elevated CRBs/subjects only",
    )
    p.add_argument(
        "--elevated-roles",
        default=",".join(DEFAULT_ELEVATED),
        help="comma-separated ClusterRole names treated as elevated "
             "(default: {})".format(",".join(DEFAULT_ELEVATED)),
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv if argv is not None else sys.argv[1:])
    configured = [x.strip() for x in args.elevated_roles.split(",") if x.strip()]

    print("# OpenShift RBAC Reference\n")
    server = oc_text(["whoami", "--show-server"])
    who = oc_text(["whoami"])
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print("_Server:_ `{}`  ·  _Whoami:_ `{}`  ·  _Generated:_ {}\n".format(
        server, who, stamp))
    print("> Point-in-time snapshot of live cluster RBAC. Values drift — "
          "regenerate before relying on specifics.\n")
    print("> Focus: **{}**. Read-only: `oc get` / `oc whoami` only — "
          "no apply.\n".format(args.focus))

    print("_Fetching RBAC objects…_", file=sys.stderr)
    data = load_rbac()
    elev_names = elevated_role_names(data, configured)

    print(section_summary(data))
    print(section_elevated(data, elev_names))

    if args.focus == "elevated":
        print("> End of elevated focus report. "
              "Re-run without `--focus elevated` for full RBAC.\n")
        return 0

    print(section_crb_subjects(data))
    print(section_clusterrolebindings(data))
    print(section_rolebindings(data))
    print(section_clusterroles(data))
    print(section_roles(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
