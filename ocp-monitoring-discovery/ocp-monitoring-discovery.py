#!/usr/bin/env python3
"""
ocp-monitoring-discovery.py — read-only inventory of OpenShift cluster
monitoring (CMO stack + related CRDs).

Purpose: same first-pass picture on every cluster (what exists, counts,
CMO knobs, scrape/rule rollup) before a deeper report.

Read-only. Runs `oc get` / `oc whoami` only. Never reads Secrets.
Requires: python3 + oc (logged in). Stdlib only.

Usage:
    python3 ocp-monitoring-discovery.py
    python3 ocp-monitoring-discovery.py > inventory.md

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


NS_NAME_RE = re.compile(
    r"monitor|prometheus|thanos|grafana|observab|telemeter|metrics|netobserv",
    re.I,
)

CRD_RE = re.compile(
    r"prometheus|alertmanager|thanos|grafana|servicemonitor|podmonitor|"
    r"^probes\.|scrapeconfig|alertmanagerconfig|thanosruler|"
    r"observability|telemeter|monitoring\.coreos|"
    r"netobserv|flowcollector|flowmetrics",
    re.I,
)

SUB_RE = re.compile(
    r"monitor|prometheus|thanos|grafana|observab|netobserv",
    re.I,
)

# Never print these keys from ConfigMaps (names or values).
REDACT_KEY_RE = re.compile(
    r"bearerToken|bearer_token|password|token:|secret:|authorization",
    re.I,
)

COUNT_KINDS = [
    ("servicemonitor", True),
    ("podmonitor", True),
    ("probe", True),
    ("prometheusrule", True),
    ("alertmanagerconfig", True),
    ("scrapeconfig", True),
    ("grafana", True),
    ("flowcollector", True),
    ("observabilityaddon", True),
]


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
    """Return stdout of `oc get ...` (wide/table) or an error line."""
    p = oc_run(args, check=False)
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip().splitlines()
        return err[-1] if err else "get-failed"
    return (p.stdout or "").rstrip() or "(empty)"


def md_table(headers, rows):
    if not rows:
        return "_no data_\n"
    h = "| " + " | ".join(headers) + " |"
    s = "|" + "|".join(["---"] * len(headers)) + "|"
    r = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([h, s] + r) + "\n"


def count_get(kind, namespaced):
    args = ["get", kind]
    if namespaced:
        args.append("-A")
    p = oc_run(args + ["-o", "name"], check=False)
    if p.returncode != 0:
        err = (p.stderr or "").lower()
        if "the server doesn't have a resource type" in err or "not found" in err:
            return "kind-missing"
        return "get-failed"
    n = sum(1 for ln in (p.stdout or "").splitlines() if ln.strip())
    return str(n)


def jsonpath_first(data, *keys, default="-"):
    cur = data
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    if cur is None or cur == "":
        return default
    return str(cur)


def section_a():
    print("## A — identity\n")
    who = oc_text(["whoami"]) or "(whoami failed)"
    server = oc_text(["whoami", "--show-server"]) or "-"
    cv = oc_json(["get", "clusterversion", "version"]) or {}
    st = cv.get("status") or {}
    desired = jsonpath_first(st, "desired", "version")
    spec = cv.get("spec") or {}
    channel = spec.get("channel") or "-"
    infra = oc_json(["get", "infrastructure", "cluster"]) or {}
    ist = infra.get("status") or {}
    print(md_table(
        ["Item", "Value"],
        [
            ["user", who],
            ["api", server],
            ["ClusterVersion object", jsonpath_first(cv, "metadata", "name")],
            ["OCP version", desired],
            ["channel", channel],
            ["Infrastructure object", jsonpath_first(infra, "metadata", "name")],
            ["infrastructureName", ist.get("infrastructureName") or "-"],
            ["platform", jsonpath_first(ist, "platformStatus", "type")],
            ["controlPlaneTopology", ist.get("controlPlaneTopology") or "-"],
            ["infrastructureTopology", ist.get("infrastructureTopology") or "-"],
        ],
    ))


def section_b():
    print("## B — operators\n")
    print("ClusterOperator `monitoring` (built-in CMO; not an OLM CSV):\n")
    print("```")
    print(oc_ok_table(["get", "co", "monitoring"]))
    print("```\n")

    print("Subscriptions whose name/CSV/channel matches monitoring-ish keywords ")
    print("(unique OLM extras — CMO will not appear here):\n")
    data = oc_json(["get", "sub", "-A"])
    rows = []
    if data:
        seen = set()
        for it in data.get("items") or []:
            md = it.get("metadata") or {}
            spec = it.get("spec") or {}
            st = it.get("status") or {}
            blob = " ".join([
                md.get("name") or "",
                md.get("namespace") or "",
                spec.get("name") or "",
                spec.get("channel") or "",
                st.get("installedCSV") or "",
            ])
            if not SUB_RE.search(blob):
                continue
            key = (
                md.get("namespace"),
                md.get("name"),
                st.get("installedCSV") or "-",
                spec.get("channel") or "-",
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(list(key))
        rows.sort()
    print(md_table(
        ["Namespace", "Subscription", "installedCSV", "channel"],
        rows,
    ))
    if not rows:
        print("_No matching subscriptions. That is normal for CMO-only clusters._\n")


def section_c():
    print("## C — namespaces (name match)\n")
    data = oc_json(["get", "ns"])
    rows = []
    if data:
        for it in data.get("items") or []:
            name = (it.get("metadata") or {}).get("name") or ""
            if NS_NAME_RE.search(name):
                st = (it.get("status") or {}).get("phase") or "-"
                created = (it.get("metadata") or {}).get("creationTimestamp") or "-"
                rows.append([name, st, created])
        rows.sort()
    print(md_table(["Namespace", "Phase", "Created"], rows))


def section_d():
    print("## D — monitoring-related CRDs\n")
    data = oc_json(["get", "crd"])
    rows = []
    if data:
        for crd in data.get("items") or []:
            name = (crd.get("metadata") or {}).get("name") or ""
            spec = crd.get("spec") or {}
            group = spec.get("group") or ""
            if not (CRD_RE.search(name) or CRD_RE.search(group)):
                continue
            if name.startswith("clusterlogforwarders."):
                continue
            kinds = spec.get("names") or {}
            versions = spec.get("versions") or []
            stored = next(
                (v.get("name") for v in versions if v.get("storage")),
                versions[0].get("name") if versions else "-",
            )
            rows.append([
                kinds.get("kind") or "-",
                group,
                spec.get("scope") or "-",
                stored or "-",
                name,
            ])
        rows.sort(key=lambda r: (r[1], r[0]))
    print(md_table(
        ["Kind", "Group", "Scope", "Version", "CRD name"],
        rows,
    ))
    print("_ClusterLogForwarder omitted (logging, not this inventory)._\n")


def section_e():
    print("## E — live instances and counts\n")
    print("### Prometheus / Alertmanager / ThanosRuler\n")
    print("```")
    print(oc_ok_table(["get", "prometheus", "-A"]))
    print("```\n```")
    print(oc_ok_table(["get", "alertmanager", "-A"]))
    print("```\n```")
    print(oc_ok_table(["get", "thanosruler", "-A"]))
    print("```\n")

    print("### Object counts\n")
    rows = []
    for kind, ns in COUNT_KINDS:
        rows.append([kind, count_get(kind, ns)])
    print(md_table(["Kind", "Count"], rows))
    print("`kind-missing` = CRD not on this cluster. `get-failed` = permission or API error.\n")


def _summarize_cm_yaml(text):
    """Pull a few knobs from CMO/UWM config.yaml. Drop credential-shaped lines."""
    if not text:
        return ["(empty config.yaml)"]
    lines = []
    for raw in text.splitlines():
        if REDACT_KEY_RE.search(raw):
            continue
        lines.append(raw.rstrip())
    keys = [
        "enableUserWorkload",
        "enableUserAlertmanagerConfig",
        "retention:",
        "storageClassName:",
        "storage:",
        "nodeSelector:",
        "node-role.kubernetes.io/master",
        "staticConfigs:",
        "externalLabels:",
        "cluster_name:",
        "environment:",
        "managed_cluster:",
        "additionalAlertmanagerConfigs:",
        "collectors:",
    ]
    interesting = []
    for ln in lines:
        stripped = ln.strip()
        if any(k in ln for k in keys) or stripped.startswith("- alertmanager-") or stripped.startswith("- http"):
            interesting.append(ln)
    if not interesting:
        return ["(no well-known knobs found; ConfigMap exists)"]
    return interesting


def section_f():
    print("## F — CMO / UWM config (ConfigMaps only; no Secrets)\n")
    print("Secret-shaped keys (bearerToken, token, password, …) are omitted.\n")

    for title, ns, name in (
        ("cluster-monitoring-config", "openshift-monitoring",
         "cluster-monitoring-config"),
        ("user-workload-monitoring-config", "openshift-user-workload-monitoring",
         "user-workload-monitoring-config"),
    ):
        print("### `{0}` (`{1}/{2}`)\n".format(title, ns, name))
        p = oc_run(["get", "cm", name, "-n", ns, "-o", "json"], check=False)
        if p.returncode != 0:
            print("_missing (often means platform defaults)._\n")
            continue
        try:
            cm = json.loads(p.stdout)
        except ValueError:
            print("_could not parse ConfigMap JSON._\n")
            continue
        raw = ((cm.get("data") or {}).get("config.yaml")) or ""
        print("```")
        print("\n".join(_summarize_cm_yaml(raw)))
        print("```\n")

    print("### Pods\n")
    print("```")
    print("openshift-monitoring:")
    print(oc_ok_table(["get", "pods", "-n", "openshift-monitoring"]))
    print("```\n```")
    print("openshift-user-workload-monitoring:")
    print(oc_ok_table(["get", "pods", "-n", "openshift-user-workload-monitoring"]))
    print("```\n")

    print("### Routes\n")
    print("```")
    print("openshift-monitoring:")
    print(oc_ok_table(["get", "route", "-n", "openshift-monitoring"]))
    print("```\n```")
    print("openshift-user-workload-monitoring:")
    print(oc_ok_table(["get", "route", "-n", "openshift-user-workload-monitoring"]))
    print("```\n")


def section_rules_scrapes():
    print("## Rules and scrapes (rollup)\n")
    print("Does **not** extract Alertmanager secret/receivers.\n")

    pr = oc_json(["get", "prometheusrule", "-A"])
    if pr:
        alerts = records = 0
        by_ns = Counter()
        for it in pr.get("items") or []:
            ns = (it.get("metadata") or {}).get("namespace") or "-"
            for g in ((it.get("spec") or {}).get("groups") or []):
                for r in g.get("rules") or []:
                    if "alert" in r:
                        alerts += 1
                        by_ns[ns] += 1
                    elif "record" in r:
                        records += 1
        print("PrometheusRule objects: **{0}** · named alerts: **{1}** · "
              "recording rules: **{2}**\n".format(
                  len(pr.get("items") or []), alerts, records))
        rows = [[str(n), ns] for ns, n in by_ns.most_common()]
        print("Named alerts by namespace:\n")
        print(md_table(["Alerts", "Namespace"], rows))
    else:
        print("_could not list PrometheusRules._\n")

    sm = oc_json(["get", "servicemonitor", "-A"])
    if sm:
        by_ns = Counter(
            (it.get("metadata") or {}).get("namespace") or "-"
            for it in sm.get("items") or []
        )
        print("ServiceMonitor objects: **{0}**\n".format(len(sm.get("items") or [])))
        print(md_table(
            ["Count", "Namespace"],
            [[str(n), ns] for ns, n in by_ns.most_common()],
        ))
    else:
        print("_could not list ServiceMonitors._\n")

    pm = oc_json(["get", "podmonitor", "-A"])
    if pm:
        print("PodMonitors:\n")
        rows = []
        for it in pm.get("items") or []:
            md = it.get("metadata") or {}
            rows.append([md.get("namespace") or "-", md.get("name") or "-"])
        rows.sort()
        print(md_table(["Namespace", "Name"], rows) if rows else "_none_\n")


def main():
    print("# OpenShift monitoring discovery\n")
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print("_Generated:_ {0}  ·  _Read-only (`oc get` / `oc whoami`). "
          "No Secrets._\n".format(stamp))
    print("> Save this file in a **private** notes repo. Do not commit live "
          "output next to this script.\n")

    section_a()
    section_b()
    section_c()
    section_d()
    section_e()
    section_f()
    section_rules_scrapes()

    print("## Notes\n")
    print("- Cluster Monitoring Operator is CVO-managed; it has no OLM CSV.\n")
    print("- Alertmanager **receivers** live in a Secret — this script does "
          "not read it. Extract separately if needed.\n")
    print("- Logging (`ClusterLogForwarder`) is out of scope.\n")


if __name__ == "__main__":
    main()
