#!/usr/bin/env python3
"""
ocp-operator-coverage-check.py — read-only report of which added operators
an ACM policy installs and configures on one managed cluster, compared with
the PolicyGenTemplates in Git.

Each installed operator gets one category:
  - ACM policy: install + config   policy installs it and creates its custom resources
  - ACM policy: install only       policy installs it, no custom resources in a policy
  - Other                          not installed by a policy (Argo CD, manual, add-on, unknown)

Extra columns (facts, no conclusions):
  - policy mode (inform / enforce) and compliance from the policy copy on the cluster
  - policy violations that name this operator's Subscription or custom resources
  - Argo CD tracking label / ACM add-on, if any
  - with --git: whether Git installs / configures it, and the Git channel vs the cluster

Sources:
  - cluster: Subscriptions, OLM Operators, CRDs, AppliedManifestWorks, and the
    ACM Policy copies the hub placed on this cluster (spec + status)
  - Git (optional): PolicyGenTemplates listed under `generators` in kustomization

Uses `oc get` and `oc whoami` only. Never reads Secrets. Never prints object
values from Git or the cluster, only kinds, names, namespaces and channels.
Requires: python3 + oc (logged in). Stdlib only, plus PyYAML when --git is used.

Usage:
    python3 ocp-operator-coverage-check.py --server https://api.example:6443 > operators.md
    python3 ocp-operator-coverage-check.py --server https://api.example:6443 \\
        --git /path/to/repo/env/policygentemplates > operators.md

Refuses to continue unless `oc whoami --show-server` matches --server.
Redirect stdout into a private notes repo. Do not commit live output here.
"""

from __future__ import print_function

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime


OLM_KINDS = {"Subscription", "OperatorGroup", "Namespace", "CatalogSource", "InstallPlan"}
ARGO_ANNOTATION = "argocd.argoproj.io/tracking-id"
ARGO_LABEL = "argocd.argoproj.io/instance"
CAT_FULL = "ACM policy: install + config"
CAT_INSTALL = "ACM policy: install only"
CAT_OTHER = "Other"


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


def oc_items(args, optional=False):
    p = oc_run(args + ["-o", "json"])
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()
        if optional and "doesn't have a resource type" in err.lower():
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
        return "_none_\n"
    head = "| " + " | ".join(headers) + " |"
    sep = "|" + "|".join(["---"] * len(headers)) + "|"
    body = []
    for row in rows:
        cells = []
        for cell in row:
            text = "-" if cell in (None, "") else str(cell)
            cells.append(text.replace("|", "\\|").replace("\n", " "))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([head, sep] + body) + "\n"


def api_group(api_version):
    return api_version.split("/")[0] if "/" in (api_version or "") else ""


def join(values):
    return ", ".join(sorted(values)) if values else "-"


# ---------------------------------------------------------------- policies


def policy_objects(policy):
    """Yield objectDefinitions from musthave / mustonlyhave templates of one Policy."""
    for tmpl in (policy.get("spec") or {}).get("policy-templates") or []:
        cfg = tmpl.get("objectDefinition") or {}
        if cfg.get("kind") != "ConfigurationPolicy":
            continue
        for obj_tmpl in (cfg.get("spec") or {}).get("object-templates") or []:
            if (obj_tmpl.get("complianceType") or "musthave").lower() == "mustnothave":
                continue
            obj = obj_tmpl.get("objectDefinition") or {}
            if obj.get("kind"):
                yield obj


def policy_flags(policy):
    """Things this script does not expand, so the reader knows."""
    flags = set()
    for tmpl in (policy.get("spec") or {}).get("policy-templates") or []:
        cfg = tmpl.get("objectDefinition") or {}
        if cfg.get("kind") == "OperatorPolicy":
            flags.add("OperatorPolicy")
        elif cfg.get("kind") == "ConfigurationPolicy" and "object-templates-raw" in (cfg.get("spec") or {}):
            flags.add("object-templates-raw")
        elif cfg.get("kind") and cfg.get("kind") != "ConfigurationPolicy":
            flags.add(cfg.get("kind"))
    return flags


def violations(policy):
    """Return the violation clauses from the latest status message of each template."""
    out = []
    for det in (policy.get("status") or {}).get("details") or []:
        hist = det.get("history") or []
        msg = (hist[0].get("message") if hist else "") or ""
        for part in msg.split(";"):
            part = part.strip()
            if part.startswith("violation"):
                out.append(part)
    return out


# ---------------------------------------------------------------- git


def read_git(root, cluster_name):
    try:
        import yaml
    except ImportError:
        die("--git needs PyYAML (pip install pyyaml)")

    def docs(path):
        with open(path) as f:
            return [d for d in yaml.safe_load_all(f) if isinstance(d, dict)]

    kust = None
    for name in ("kustomization.yml", "kustomization.yaml"):
        if os.path.exists(os.path.join(root, name)):
            kust = docs(os.path.join(root, name))[0]
    if kust is None:
        die("no kustomization.yml in {0}".format(root))

    pgts = []
    for gen in kust.get("generators") or []:
        pgts += [p for p in docs(os.path.join(root, gen)) if p.get("kind") == "PolicyGenTemplate"]

    # Per-cluster PolicyGenTemplates are bound by a label whose value is the
    # cluster name. Find that label from this cluster's own PolicyGenTemplate,
    # then skip the ones that use the same label for another cluster.
    cluster_keys = set()
    for pgt in pgts:
        for k, v in ((pgt.get("spec") or {}).get("bindingRules") or {}).items():
            if v == cluster_name:
                cluster_keys.add(k)

    used, skipped, problems, objects = [], [], [], []
    for pgt in pgts:
        meta = pgt.get("metadata") or {}
        spec = pgt.get("spec") or {}
        pgt_name = meta.get("name") or ""
        rules = spec.get("bindingRules") or {}
        if any(k in rules and rules[k] != cluster_name for k in cluster_keys):
            skipped.append(pgt_name)
            continue
        used.append(pgt_name)
        for sf in spec.get("sourceFiles") or []:
            fn = sf.get("fileName") or ""
            path = os.path.join(root, "source-crs", fn)
            if not os.path.exists(path):
                problems.append("{0}: source file missing: {1}".format(pgt_name, fn))
                continue
            try:
                found = docs(path)
            except Exception as e:  # noqa: BLE001
                problems.append("{0}: cannot parse {1}: {2}".format(pgt_name, fn, str(e).splitlines()[0]))
                continue
            sf_meta = sf.get("metadata") or {}
            sf_spec = sf.get("spec") or {}
            for d in found:
                md = d.get("metadata") or {}
                spec_d = d.get("spec") or {}
                is_sub = d.get("kind") == "Subscription"
                if sf.get("policyName"):
                    pol = "{0}.{1}-{2}".format(meta.get("namespace") or "", pgt_name, sf.get("policyName"))
                elif d.get("kind") == "Policy":
                    # a ready-made Policy passed through as is
                    pol = "{0}.{1}".format(md.get("namespace") or meta.get("namespace") or "", md.get("name") or "")
                else:
                    pol = ""
                objects.append({
                    "policy": pol,
                    "kind": d.get("kind"),
                    "group": api_group(d.get("apiVersion")),
                    "ns": sf_meta.get("namespace") or md.get("namespace") or "",
                    "name": sf_meta.get("name") or md.get("name") or "",
                    "package": (sf_spec.get("name") or spec_d.get("name") or "") if is_sub else "",
                    "channel": (sf_spec.get("channel") or spec_d.get("channel") or "") if is_sub else "",
                })
    return used, skipped, problems, objects


# ---------------------------------------------------------------- main


def main():
    parser = argparse.ArgumentParser(description="Read-only operator vs ACM policy (and Git) report")
    parser.add_argument("--server", required=True, help="API server URL that oc must already be logged into")
    parser.add_argument("--git", help="path to a policygentemplates folder (with kustomization.yml)")
    args = parser.parse_args()

    expected = norm_server(args.server)
    who = oc_run(["whoami"])
    server = oc_run(["whoami", "--show-server"])
    if who.returncode != 0 or server.returncode != 0:
        die("oc whoami failed. Log in before running this script.")
    actual = norm_server(server.stdout)
    if actual != expected:
        die("refusing: oc server is {0}, --server is {1}".format(actual, expected))

    subs = oc_items(["get", "subscriptions.operators.coreos.com", "-A"])
    olm_ops = oc_items(["get", "operators.operators.coreos.com"])
    policies = oc_items(["get", "policies.policy.open-cluster-management.io", "-A"], optional=True)
    works = oc_items(["get", "appliedmanifestworks.work.open-cluster-management.io"], optional=True)
    crds = oc_items(["get", "customresourcedefinitions"])

    crd_by_kind = {}
    for c in crds:
        spec = c.get("spec") or {}
        crd_by_kind[(spec.get("group") or "", (spec.get("names") or {}).get("kind") or "")] = \
            (c.get("metadata") or {}).get("name") or ""

    olm_refs = {}
    for op in olm_ops:
        name = (op.get("metadata") or {}).get("name") or ""
        olm_refs[name] = ((op.get("status") or {}).get("components") or {}).get("refs") or []

    work_subs = set()
    for work in works:
        for res in (work.get("status") or {}).get("appliedResources") or []:
            if res.get("resource") == "subscriptions" and res.get("group") == "operators.coreos.com":
                work_subs.add((res.get("namespace") or "", res.get("name") or ""))

    # policy copies on this cluster
    cluster_name = ""
    pol_info = {}
    pol_subs, pol_deploys, pol_crs = {}, {}, []
    pol_crd_kinds = {}
    for pol in policies:
        meta = pol.get("metadata") or {}
        name = meta.get("name") or ""
        cluster_name = cluster_name or meta.get("namespace") or ""
        pol_info[name] = {
            "mode": (pol.get("spec") or {}).get("remediationAction") or "-",
            "disabled": bool((pol.get("spec") or {}).get("disabled")),
            "status": (pol.get("status") or {}).get("compliant") or "-",
            "violations": violations(pol),
            "flags": policy_flags(pol),
        }
        for obj in policy_objects(pol):
            kind = obj.get("kind")
            om = obj.get("metadata") or {}
            group = api_group(obj.get("apiVersion"))
            ns = om.get("namespace") or ""
            if kind == "Subscription" and group == "operators.coreos.com":
                pkg = (obj.get("spec") or {}).get("name") or om.get("name") or ""
                pol_subs.setdefault((ns, pkg), set()).add(name)
            elif kind == "Deployment" and (om.get("name") or "").endswith("-operator"):
                pol_deploys.setdefault((ns, om.get("name")), set()).add(name)
            elif kind == "CustomResourceDefinition":
                s = obj.get("spec") or {}
                pol_crd_kinds.setdefault(name, set()).add((s.get("group") or "", (s.get("names") or {}).get("kind") or ""))
            elif kind not in OLM_KINDS and group:
                pol_crs.append((name, group, kind))

    # installed operators
    installed, not_counted = [], []
    for sub in subs:
        meta = sub.get("metadata") or {}
        spec = sub.get("spec") or {}
        ns = meta.get("namespace") or ""
        pkg = spec.get("name") or ""
        csv = (sub.get("status") or {}).get("installedCSV") or ""
        refs = olm_refs.get("{0}.{1}".format(pkg, ns)) or []
        csv_refs = [r.get("name") for r in refs if r.get("kind") == "ClusterServiceVersion"]
        if not csv:
            not_counted.append([pkg, ns, "Subscription has no installed CSV"])
            continue
        if csv not in csv_refs:
            not_counted.append([pkg, ns, "Subscription names {0}, but that CSV is not present".format(csv)])
            continue
        ann = meta.get("annotations") or {}
        labels = meta.get("labels") or {}
        installed.append({
            "pkg": pkg, "ns": ns, "sub": meta.get("name") or pkg, "type": "OLM", "csv": csv,
            "channel": spec.get("channel") or "-",
            "policies": pol_subs.get((ns, pkg)) or set(),
            "argo": bool(ann.get(ARGO_ANNOTATION) or labels.get(ARGO_LABEL)),
            "addon": (ns, meta.get("name") or "") in work_subs,
            "crd_names": {r.get("name") for r in refs if r.get("kind") == "CustomResourceDefinition"},
            "crd_kinds": None,
        })
    for (ns, name), pols in sorted(pol_deploys.items()):
        p = oc_run(["get", "deployment", name, "-n", ns, "-o", "json"])
        if p.returncode != 0:
            not_counted.append([name, ns, "a policy names this Deployment, but it is not on the cluster"])
            continue
        kinds = set()
        for pol in pols:
            kinds |= pol_crd_kinds.get(pol) or set()
        installed.append({
            "pkg": name, "ns": ns, "sub": name, "type": "Deployment", "csv": "-", "channel": "-",
            "policies": pols, "argo": False, "addon": False,
            "crd_names": {crd_by_kind.get(k) for k in kinds if crd_by_kind.get(k)}, "crd_kinds": kinds,
        })

    def owns(item, group, kind):
        if item["crd_kinds"] is not None:
            return (group, kind) in item["crd_kinds"]
        return crd_by_kind.get((group, kind)) in item["crd_names"]

    # git
    git = None
    if args.git:
        used, skipped, problems, gobjs = read_git(args.git, cluster_name)
        git = {"used": used, "skipped": skipped, "problems": problems,
               "subs": {}, "deploys": set(), "crd_kinds": set(), "crs": [], "policies": set()}
        for o in gobjs:
            if o["policy"]:
                git["policies"].add(o["policy"])
            if o["kind"] == "Subscription" and o["group"] == "operators.coreos.com":
                git["subs"][(o["ns"], o["package"] or o["name"])] = o["channel"] or "-"
            elif o["kind"] == "Deployment" and o["name"].endswith("-operator"):
                git["deploys"].add((o["ns"], o["name"]))
            elif o["kind"] not in OLM_KINDS and o["group"]:
                git["crs"].append((o["group"], o["kind"]))

    # classify
    for item in installed:
        item["cfg"] = sorted({kind for _, group, kind in pol_crs if owns(item, group, kind)})
        if item["policies"]:
            item["cat"] = CAT_FULL if item["cfg"] else CAT_INSTALL
        else:
            item["cat"] = CAT_OTHER
        modes = {pol_info[p]["mode"] for p in item["policies"]}
        states = {pol_info[p]["status"] for p in item["policies"]}
        item["mode"] = join(modes)
        item["status"] = join(states)
        # Custom-resource clauses only count for operators a policy installs,
        # so a CRD plural that clashes with another kind ("subscriptions") is ignored.
        plurals = {n.split(".")[0] for n in item["crd_names"] if n} if item["policies"] else set()
        plurals.discard("subscriptions")
        hits = set()
        sub_re = re.compile(r"^violation - subscriptions\b.*\[[^\]]*\b{0}\b".format(re.escape(item["sub"])))
        for pol, info in pol_info.items():
            for v in info["violations"]:
                ns_m = re.search(r"in namespace (\S+)", v)
                if sub_re.search(v) and (not ns_m or ns_m.group(1) == item["ns"]):
                    hits.add("Subscription")
                for pl in plurals:
                    if re.search(r"^violation - {0}\b".format(re.escape(pl)), v):
                        hits.add(pl)
        item["viol"] = join(hits)
        other = []
        if item["argo"]:
            other.append("Argo CD label")
        if item["addon"]:
            other.append("ACM add-on")
        item["source"] = ", ".join(other) or "-"
        if git is not None:
            key = (item["ns"], item["pkg"])
            in_git = key in git["subs"] or key in git["deploys"]
            item["git_install"] = "yes" if in_git else "no"
            item["git_cfg"] = "yes" if any(owns(item, g, k) for g, k in git["crs"]) else "no"
            item["git_channel"] = git["subs"].get(key, "-")

    # ------------------------------------------------------------ output
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print("# Operator coverage check\n")
    print("_Server:_ `{0}`  ·  _Cluster:_ `{1}`  ·  _Generated:_ {2}  ·  _Read-only (`oc get` / `oc whoami`)._\n"
          .format(actual, cluster_name or "-", stamp))
    print("> Save this file in a **private** notes repo. Do not commit live output next to this script.\n")

    print("## 1. Summary\n")
    counts = {c: sum(1 for i in installed if i["cat"] == c) for c in (CAT_FULL, CAT_INSTALL, CAT_OTHER)}
    print(md_table(["Category", "Operators"],
                   [[c, n] for c, n in counts.items()] + [["**Total installed**", "**{0}**".format(len(installed))]]))
    print("Policies on this cluster: **{0}** ({1} NonCompliant, {2} disabled)\n".format(
        len(pol_info),
        sum(1 for p in pol_info.values() if p["status"] == "NonCompliant"),
        sum(1 for p in pol_info.values() if p["disabled"])))

    print("## 2. Operators\n")
    heads = ["Category", "Operator", "Namespace", "Installed CSV", "Channel", "Policy",
             "Policy mode", "Policy status", "Violations naming it", "Config kinds in policy", "Other source"]
    if git is not None:
        heads += ["In Git: install", "In Git: config", "Git channel"]
    order = {CAT_FULL: 0, CAT_INSTALL: 1, CAT_OTHER: 2}
    rows = []
    for i in sorted(installed, key=lambda x: (order[x["cat"]], x["pkg"], x["ns"])):
        row = [i["cat"], i["pkg"], i["ns"], i["csv"], i["channel"], join(i["policies"]),
               i["mode"] if i["policies"] else "-", i["status"] if i["policies"] else "-",
               i["viol"], join(i["cfg"]), i["source"]]
        if git is not None:
            row += [i["git_install"], i["git_cfg"], i["git_channel"]]
        rows.append(row)
    print(md_table(heads, rows))

    print("## 3. Policies on this cluster\n")
    print(md_table(["Policy", "Mode", "Disabled", "Status", "Violation clauses", "Not expanded by this script"],
                   [[n, p["mode"], "yes" if p["disabled"] else "no", p["status"], len(p["violations"]),
                     join(p["flags"])] for n, p in sorted(pol_info.items())]))

    if git is not None:
        print("## 4. Git vs cluster\n")
        print("Git folder: `{0}`\n".format(os.path.basename(os.path.dirname(os.path.abspath(args.git)))
                                            + "/" + os.path.basename(os.path.abspath(args.git))))
        print("PolicyGenTemplates read: {0}. Skipped (other cluster): {1}.\n".format(
            join(git["used"]), join(git["skipped"])))
        if git["problems"]:
            print("**Git read problems**\n")
            for p in git["problems"]:
                print("- " + p)
            print()
        inst_keys = {(i["ns"], i["pkg"]) for i in installed}
        diffs = []
        for key, ch in sorted(git["subs"].items()):
            if key not in inst_keys:
                diffs.append([key[1], key[0], "in Git, not installed on the cluster"])
        for key in sorted(git["deploys"]):
            if key not in inst_keys:
                diffs.append([key[1], key[0], "in Git (Deployment), not on the cluster"])
        for i in installed:
            key = (i["ns"], i["pkg"])
            if i["policies"] and i.get("git_install") == "no":
                diffs.append([i["pkg"], i["ns"], "installed by a policy on the cluster, not in Git"])
            if i.get("git_channel", "-") not in ("-", i["channel"]) and i["channel"] != "-":
                diffs.append([i["pkg"], i["ns"], "channel: Git {0}, cluster {1}".format(i["git_channel"], i["channel"])])
        cluster_pols = set(pol_info)
        for p in sorted(git["policies"] - cluster_pols):
            diffs.append([p, "-", "policy in Git, no copy on this cluster"])
        print(md_table(["Item", "Namespace", "Difference"], diffs))

    print("## 5. Not counted\n")
    print(md_table(["Package", "Namespace", "Reason"], not_counted))

    print("## Notes\n")
    print("- Installed = OLM Subscription with its CSV present, or an operator Deployment a policy creates. "
          "Platform ClusterOperators are not counted. The same operator in two namespaces counts twice.")
    print("- Config = a policy creates objects of a kind this operator's CRDs define.")
    print("- Policy mode and status come from the policy copy on this cluster. They are shown as facts; "
          "`inform` policies report drift and do not fix it.")
    print("- Only `object-templates` are expanded. Policies with `object-templates-raw` or other template "
          "kinds are listed in section 3.")
    print("- Secrets are never read. No object values are printed.")


if __name__ == "__main__":
    main()
