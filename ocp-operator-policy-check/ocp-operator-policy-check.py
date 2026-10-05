#!/usr/bin/env python3
"""
ocp-operator-policy-check.py — read-only report of which added operators an
ACM policy installs and configures on one managed cluster.

Installed operators come from OLM Subscriptions whose installed CSV still
exists, plus plain operator Deployments that a policy creates. Coverage comes
from the ACM Policies replicated onto this cluster, so it is what the hub
actually placed here, not what a Git checkout says should be placed.

Platform operators (`oc get clusteroperators`) are not counted. They ship with
the OpenShift release.

Uses `oc get` and `oc whoami` only. Never reads Secrets.
Requires: python3 + oc (logged in). Stdlib only.

Usage:
    python3 ocp-operator-policy-check.py --server https://api.example:6443
    python3 ocp-operator-policy-check.py --server https://api.example:6443 > operators.md

Refuses to continue unless `oc whoami --show-server` matches --server.
Redirect stdout into a private notes repo. Do not commit live output here.
"""

from __future__ import print_function

import argparse
import json
import subprocess
import sys


OLM_KINDS = {"Subscription", "OperatorGroup", "Namespace", "CatalogSource", "InstallPlan"}
ARGO_ANNOTATION = "argocd.argoproj.io/tracking-id"
ARGO_LABEL = "argocd.argoproj.io/instance"


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


def api_group(api_version):
    if not api_version or "/" not in api_version:
        return ""
    return api_version.split("/", 1)[0]


def policy_objects(policies):
    """Yield (policy, object) for every musthave/mustonlyhave object template."""
    for pol in policies:
        meta = pol.get("metadata") or {}
        pol_name = "{0}/{1}".format(meta.get("namespace") or "", meta.get("name") or "")
        for tmpl in (pol.get("spec") or {}).get("policy-templates") or []:
            cfg = tmpl.get("objectDefinition") or {}
            if cfg.get("kind") != "ConfigurationPolicy":
                continue
            cfg_spec = cfg.get("spec") or {}
            for obj_tmpl in cfg_spec.get("object-templates") or []:
                compliance = (obj_tmpl.get("complianceType") or "musthave").lower()
                if compliance == "mustnothave":
                    continue
                obj = obj_tmpl.get("objectDefinition") or {}
                if obj.get("kind"):
                    yield pol_name, obj


def main():
    parser = argparse.ArgumentParser(description="Read-only operator vs ACM policy report")
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

    subs = oc_json(["get", "subscriptions.operators.coreos.com", "-A"]).get("items") or []
    olm_ops = oc_json(["get", "operators.operators.coreos.com"]).get("items") or []
    policies = oc_json(["get", "policies.policy.open-cluster-management.io", "-A"], optional=True).get("items") or []
    works = oc_json(["get", "appliedmanifestworks.work.open-cluster-management.io"], optional=True).get("items") or []

    crd_p = oc_run([
        "get", "crd", "--no-headers",
        "-o", "custom-columns=NAME:.metadata.name,GROUP:.spec.group,KIND:.spec.names.kind",
    ])
    if crd_p.returncode != 0:
        die("oc get crd failed")
    crd_by_kind = {}
    for line in crd_p.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            crd_by_kind[(parts[1], parts[2])] = parts[0]

    # OLM Operator objects are named <package>.<namespace>.
    olm_refs = {}
    for op in olm_ops:
        name = (op.get("metadata") or {}).get("name") or ""
        refs = ((op.get("status") or {}).get("components") or {}).get("refs") or []
        olm_refs[name] = refs

    work_subs = set()
    for work in works:
        for res in (work.get("status") or {}).get("appliedResources") or []:
            if res.get("resource") == "subscriptions" and res.get("group") == "operators.coreos.com":
                work_subs.add((res.get("namespace") or "", res.get("name") or ""))

    pol_subs = {}
    pol_deploys = {}
    pol_crds = {}
    pol_crs = []
    for pol_name, obj in policy_objects(policies):
        kind = obj.get("kind")
        meta = obj.get("metadata") or {}
        ns = meta.get("namespace") or ""
        name = meta.get("name") or ""
        group = api_group(obj.get("apiVersion"))
        if kind == "Subscription" and group == "operators.coreos.com":
            pkg = (obj.get("spec") or {}).get("name") or name
            pol_subs.setdefault((ns, pkg), set()).add(pol_name)
        elif kind == "Deployment" and name.endswith("-operator"):
            pol_deploys.setdefault((ns, name), set()).add(pol_name)
        elif kind == "CustomResourceDefinition":
            spec = obj.get("spec") or {}
            crd_group = spec.get("group") or ""
            crd_kind = (spec.get("names") or {}).get("kind") or ""
            if crd_group and crd_kind:
                pol_crds.setdefault(pol_name, set()).add((crd_group, crd_kind))
        elif kind not in OLM_KINDS and group:
            pol_crs.append((pol_name, group, kind, ns, name))

    installed = []
    not_counted = []
    for sub in subs:
        meta = sub.get("metadata") or {}
        spec = sub.get("spec") or {}
        status = sub.get("status") or {}
        ns = meta.get("namespace") or ""
        pkg = spec.get("name") or ""
        csv = status.get("installedCSV") or ""
        refs = olm_refs.get("{0}.{1}".format(pkg, ns)) or []
        csv_refs = [r.get("name") for r in refs if r.get("kind") == "ClusterServiceVersion"]
        if not csv:
            not_counted.append([pkg, ns, "Subscription has no installed CSV"])
            continue
        if csv not in csv_refs:
            not_counted.append([pkg, ns, "Subscription names {0}, but that CSV is not present".format(csv)])
            continue
        owned = set(r.get("name") for r in refs if r.get("kind") == "CustomResourceDefinition")
        ann = meta.get("annotations") or {}
        labels = meta.get("labels") or {}
        argo = ann.get(ARGO_ANNOTATION) or labels.get(ARGO_LABEL) or ""
        installed.append({
            "pkg": pkg,
            "ns": ns,
            "type": "OLM",
            "csv": csv,
            "policies": sorted(pol_subs.get((ns, pkg)) or []),
            "argo": argo,
            "addon": (ns, meta.get("name") or "") in work_subs,
            "owned": owned,
            "kind_set": None,
        })

    for (ns, name), pols in sorted(pol_deploys.items()):
        dep = oc_json(["get", "deployment", name, "-n", ns], optional=True)
        if not dep.get("metadata"):
            not_counted.append([name, ns, "policy names this Deployment, but it is not on the cluster"])
            continue
        ready = (dep.get("status") or {}).get("readyReplicas") or 0
        kinds = set()
        for pol in pols:
            kinds |= pol_crds.get(pol) or set()
        installed.append({
            "pkg": name,
            "ns": ns,
            "type": "Deployment (ready {0})".format(ready),
            "csv": "",
            "policies": sorted(pols),
            "argo": "",
            "addon": False,
            "owned": set(),
            "kind_set": kinds,
        })

    for item in installed:
        cfg = set()
        for pol_name, group, kind, ns, name in pol_crs:
            if item["kind_set"] is not None:
                hit = (group, kind) in item["kind_set"]
            else:
                hit = crd_by_kind.get((group, kind)) in item["owned"]
            if hit:
                cfg.add(kind)
        item["config"] = sorted(cfg)
        if item["policies"]:
            item["source"] = "ACM policy"
        elif item["argo"]:
            item["source"] = "Argo CD"
        elif item["addon"]:
            item["source"] = "ACM add-on"
        else:
            item["source"] = "none found"

    in_policy = [i for i in installed if i["source"] == "ACM policy"]
    outside = [i for i in installed if i["source"] != "ACM policy"]
    with_cfg = [i for i in in_policy if i["config"]]

    sub_keys = set("{0}.{1}".format((s.get("spec") or {}).get("name") or "", (s.get("metadata") or {}).get("namespace") or "") for s in subs)
    leftover_empty = 0
    leftover_crds = []
    for name, refs in sorted(olm_refs.items()):
        if name in sub_keys:
            continue
        if any(r.get("kind") == "ClusterServiceVersion" for r in refs):
            continue
        if refs:
            leftover_crds.append([name, len(refs)])
        else:
            leftover_empty += 1

    clusterops = oc_run(["get", "clusteroperators", "--no-headers"])
    platform = len([l for l in clusterops.stdout.splitlines() if l.strip()]) if clusterops.returncode == 0 else "-"

    print("# Operators vs ACM policy\n")
    print("Installed means an OLM Subscription whose CSV is present, or an operator Deployment a policy creates. "
          "Coverage is the ACM Policies replicated onto this cluster.\n")
    print(md_table(["Item", "Value"], [
        ["user", (who.stdout or "").strip()],
        ["api", actual],
        ["ACM policies on this cluster", len(policies)],
        ["platform ClusterOperators (not counted)", platform],
        ["OLM Operator objects (oc get operators)", len(olm_ops)],
        ["Subscriptions", len(subs)],
    ]))

    print("\n## Summary\n")
    print(md_table(["Installed operators", "Count"], [
        ["In an ACM policy", len(in_policy)],
        ["- with config objects in a policy", len(with_cfg)],
        ["- install only", len(in_policy) - len(with_cfg)],
        ["Not in an ACM policy", len(outside)],
        ["- in Git through Argo CD", len([i for i in outside if i["source"] == "Argo CD"])],
        ["- ACM add-on (ManifestWork)", len([i for i in outside if i["source"] == "ACM add-on"])],
        ["- no Git source found", len([i for i in outside if i["source"] == "none found"])],
        ["Total installed", len(installed)],
    ]))

    def rows(items):
        out = []
        for i in sorted(items, key=lambda x: (x["pkg"], x["ns"])):
            out.append([
                i["pkg"], i["ns"], i["type"], i["csv"], i["source"],
                ", ".join(i["policies"]), i["argo"], ", ".join(i["config"]),
            ])
        return out

    headers = ["Package", "Namespace", "Type", "CSV", "Source", "Policy", "Argo tracking", "Config kinds in policy"]
    print("\n## In an ACM policy\n")
    print(md_table(headers, rows(in_policy)))
    print("\n## Not in an ACM policy\n")
    print(md_table(headers, rows(outside)))

    print("\n## Not counted as installed\n")
    print(md_table(["Package", "Namespace", "Reason"], sorted(not_counted)))

    print("\n## OLM Operator objects with no Subscription and no CSV\n")
    print("Leftovers from removed installs. Not running.\n")
    print(md_table(["Item", "Value"], [
        ["empty", leftover_empty],
        ["only CRDs or other refs left", len(leftover_crds)],
    ]))
    print(md_table(["Operator object", "Refs"], leftover_crds))


if __name__ == "__main__":
    main()
