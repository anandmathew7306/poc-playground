#!/usr/bin/env python3
"""
ocp-net-extended-report.py — generate an Extended Networking reference report
for an OpenShift cluster.

Covers:
  - OVN EgressIP (+ egress-assignable node labels)
  - Multus NetworkAttachmentDefinition (NAD)
  - Whereabouts IPPool (and related counts)
  - MultiNetworkPolicy

MetalLB / EgressService: sibling ocp-net-metallb-report.
Host/node underlay: sibling ocp-net-core-report.

Read-only. Runs `oc get ... -o json` and prints markdown tables.
Requires: python3 + oc (logged in). No pip packages.

Usage:
    python3 ocp-net-extended-report.py                 # stdout
    python3 ocp-net-extended-report.py > report.md     # save
"""

import json
import subprocess
import sys
from datetime import datetime


def oc_json(args):
    """Run `oc <args> -o json` and return parsed JSON (or None on failure)."""
    cmd = ["oc"] + args + ["-o", "json"]
    try:
        out = subprocess.run(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, universal_newlines=True,
                             check=True)
        return json.loads(out.stdout)
    except subprocess.CalledProcessError as e:
        print(f"  > command failed: {' '.join(cmd)}", file=sys.stderr)
        err = (e.stderr or "").strip()
        if err:
            print(f"  > {err.splitlines()[-1]}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"  > could not parse JSON: {' '.join(cmd)}", file=sys.stderr)
        return None


def oc_text(args):
    try:
        return subprocess.run(["oc"] + args, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,
                              universal_newlines=True).stdout.strip()
    except Exception:
        return ""


def md_table(headers, rows):
    if not rows:
        return "_no data_\n"
    h = "| " + " | ".join(headers) + " |"
    s = "|" + "|".join(["---"] * len(headers)) + "|"
    r = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([h, s] + r) + "\n"


def fmt_label_selector(sel):
    """Compact LabelSelector → readable string."""
    if not sel:
        return "(none)"
    if not isinstance(sel, dict):
        return str(sel)
    parts = []
    ml = sel.get("matchLabels") or {}
    if ml:
        parts.append(",".join(f"{k}={v}" for k, v in sorted(ml.items())))
    for expr in sel.get("matchExpressions") or []:
        key = expr.get("key", "?")
        op = expr.get("operator", "?")
        vals = ",".join(expr.get("values") or [])
        parts.append(f"{key} {op} [{vals}]" if vals else f"{key} {op}")
    return "; ".join(parts) if parts else "(none)"


def short_host(name):
    """Strip long FQDN noise for tables — keep first label."""
    if not name or name == "-":
        return name or "-"
    return name.split(".")[0]


def nad_cni_type(config_str):
    """Best-effort CNI type from NAD spec.config JSON string."""
    if not config_str:
        return "-"
    try:
        cfg = json.loads(config_str)
    except (TypeError, ValueError, json.JSONDecodeError):
        return "(unparsed)"
    if isinstance(cfg, dict):
        t = cfg.get("type")
        if t:
            return t
        plugins = cfg.get("plugins")
        if isinstance(plugins, list) and plugins:
            types = [p.get("type") for p in plugins
                     if isinstance(p, dict) and p.get("type")]
            return "+".join(types) if types else "(plugins)"
    return "(unknown)"


def nad_summary(config_str, limit=80):
    """One-line truncated config for the sheet (not a full dump)."""
    if not config_str:
        return "-"
    s = " ".join(str(config_str).split())
    if len(s) > limit:
        return s[: limit - 1] + "…"
    return s


# ---------- EgressIP ----------
def egress_ips():
    d = oc_json(["get", "egressips"])
    if not d:
        return ("## EgressIP\n\n"
                "_could not retrieve (k8s.ovn.org) — CRD missing or no access_\n")
    rows = []
    for item in d.get("items", []):
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        status = item.get("status", {}) or {}
        eips = ", ".join(spec.get("egressIPs") or []) or "-"
        ns_sel = fmt_label_selector(spec.get("namespaceSelector"))
        pod_sel = fmt_label_selector(spec.get("podSelector"))
        assigned = []
        for it in status.get("items") or []:
            if not isinstance(it, dict):
                continue
            ip = it.get("egressIP") or "?"
            node = short_host(it.get("node") or "-")
            assigned.append(f"{ip}@{node}")
        rows.append([
            meta.get("name", ""),
            eips,
            ns_sel,
            pod_sel,
            ", ".join(assigned) if assigned else "(unassigned)",
        ])
    rows.sort(key=lambda r: r[0])
    return ("## EgressIP\n\n"
            "_OVN SNAT egress IPs for selected namespaces/pods. "
            "**Not** MetalLB EgressService (LB VIP symmetric egress)._\n\n"
            + md_table(
                ["Name", "egressIPs", "namespaceSelector", "podSelector",
                 "status (IP@node)"],
                rows,
            ))


def egress_assignable_nodes():
    """Nodes and k8s.ovn.org/egress-assignable label (ACS incident lesson)."""
    d = oc_json(["get", "nodes"])
    if not d:
        return ("## Egress-assignable nodes\n\n"
                "_could not retrieve nodes_\n")
    key = "k8s.ovn.org/egress-assignable"
    rows = []
    disabled = 0
    enabled = 0
    missing = 0
    for item in d.get("items", []):
        meta = item.get("metadata", {}) or {}
        labels = meta.get("labels") or {}
        name = short_host(meta.get("name", ""))
        if key not in labels:
            val = "(absent)"
            missing += 1
        else:
            val = labels.get(key) if labels.get(key) != "" else '"" (empty=enabled)'
            # OVN: presence with empty or non-false typically allows assignment;
            # explicit "false" disables (see ACS troubleshooting notes).
            if str(labels.get(key)).lower() == "false":
                disabled += 1
            else:
                enabled += 1
        # also surface non-standard helper label if present
        extra = labels.get("egress-node") or "-"
        rows.append([name, val, extra])
    rows.sort(key=lambda r: r[0])
    note = (f"_Label `{key}`: empty/absent/true-ish → assignable; "
            f"`false` → disabled. "
            f"Counts: enabled-ish={enabled}, false={disabled}, "
            f"absent={missing}. "
            f"`egress-node` is non-standard (shown if set)._\n\n")
    return ("## Egress-assignable nodes\n\n" + note
            + md_table(["Node", "egress-assignable", "egress-node (extra)"],
                       rows))


# ---------- Multus NAD ----------
def network_attachment_definitions():
    d = oc_json(["get", "network-attachment-definitions", "-A"])
    if not d:
        return ("## NetworkAttachmentDefinitions\n\n"
                "_could not retrieve (k8s.cni.cncf.io)_\n")
    rows = []
    for item in d.get("items", []):
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        cfg = spec.get("config") or ""
        rows.append([
            meta.get("namespace", ""),
            meta.get("name", ""),
            nad_cni_type(cfg),
            nad_summary(cfg),
        ])
    rows.sort(key=lambda r: (r[0], r[1]))
    return ("## NetworkAttachmentDefinitions\n\n"
            "_Multus secondary / additional networks (NAD). "
            "Config column is truncated — not a full CNI dump._\n\n"
            + md_table(["Namespace", "Name", "CNI type", "config (short)"],
                       rows))


# ---------- Whereabouts ----------
def whereabouts_ippools():
    d = oc_json(["get", "ippools.whereabouts.cni.cncf.io", "-A"])
    if not d:
        return ("## Whereabouts IPPools\n\n"
                "_could not retrieve (whereabouts.cni.cncf.io) — "
                "CRD missing, empty, or no access_\n")
    rows = []
    for item in d.get("items", []):
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        # common fields: range, allocations (map)
        rng = spec.get("range") or spec.get("Range") or "-"
        allocs = spec.get("allocations") or {}
        n_alloc = len(allocs) if isinstance(allocs, dict) else "-"
        rows.append([
            meta.get("namespace", ""),
            meta.get("name", ""),
            rng,
            str(n_alloc),
        ])
    rows.sort(key=lambda r: (r[0], r[1]))
    return ("## Whereabouts IPPools\n\n"
            "_IPAM pools for Multus secondary interfaces (Whereabouts)._\n\n"
            + md_table(["Namespace", "Name", "range", "allocations"], rows))


def whereabouts_related_counts():
    """Counts only for quieter Whereabouts CRDs."""
    kinds = [
        ("OverlappingRangeIPReservation",
         ["get", "overlappingrangeipreservations.whereabouts.cni.cncf.io",
          "-A"]),
        ("NodeSlicePool",
         ["get", "nodeslicepools.whereabouts.cni.cncf.io", "-A"]),
        ("IPAMClaim (k8s.cni.cncf.io)",
         ["get", "ipamclaims.k8s.cni.cncf.io", "-A"]),
    ]
    rows = []
    for label, args in kinds:
        d = oc_json(args)
        if d is None:
            rows.append([label, "get-failed"])
        else:
            rows.append([label, str(len(d.get("items", [])))])
    return ("## Whereabouts / IPAM (related counts)\n\n"
            "_Noise control — counts only._\n\n"
            + md_table(["Kind", "Count"], rows))


# ---------- MultiNetworkPolicy ----------
def multi_network_policies():
    d = oc_json(["get", "multi-networkpolicies.k8s.cni.cncf.io", "-A"])
    if not d:
        return ("## MultiNetworkPolicies\n\n"
                "_could not retrieve (k8s.cni.cncf.io) — "
                "CRD missing, empty, or no access_\n")
    rows = []
    for item in d.get("items", []):
        meta = item.get("metadata", {}) or {}
        spec = item.get("spec", {}) or {}
        types = ", ".join(spec.get("policyTypes") or []) or "-"
        pod = fmt_label_selector(spec.get("podSelector"))
        # annotation often names the NAD
        anns = meta.get("annotations") or {}
        net = (anns.get("k8s.v1.cni.cncf.io/policy-for")
               or anns.get("k8s.v1.cni.cncf.io/networks")
               or "-")
        rows.append([
            meta.get("namespace", ""),
            meta.get("name", ""),
            types,
            pod,
            net,
        ])
    rows.sort(key=lambda r: (r[0], r[1]))
    return ("## MultiNetworkPolicies\n\n"
            "_NetworkPolicy-like rules for Multus secondary networks._\n\n"
            + md_table(
                ["Namespace", "Name", "policyTypes", "podSelector",
                 "policy-for / networks ann"],
                rows,
            ))


def main():
    print("# OpenShift Network Reference — Extended Networking\n")
    server = oc_text(["whoami", "--show-server"])
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    print(f"_Server:_ `{server}`  ·  _Generated:_ {stamp}\n")
    print("> Point-in-time snapshot of live cluster state. Values drift — "
          "regenerate before relying on specifics.\n")
    print("> Scope: OVN **EgressIP**, Multus **NAD**, **Whereabouts**, "
          "**MultiNetworkPolicy**. "
          "**Not in scope:** host underlay (core), MetalLB / EgressService "
          "(MetalLB report).\n")
    print("> Read-only: `oc get` / `oc whoami` only — no apply.\n")

    eip = egress_ips()
    if "_could not retrieve" in eip and "EgressIP" in eip:
        # soft-fail: still print other sections if EgressIP API missing
        pass

    print(eip)
    print(egress_assignable_nodes())
    print(network_attachment_definitions())
    print(whereabouts_ippools())
    print(whereabouts_related_counts())
    print(multi_network_policies())


if __name__ == "__main__":
    main()
