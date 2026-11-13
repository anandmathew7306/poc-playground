#!/usr/bin/env python3
"""Read-only snapshot of OpenShift log forwarding on the cluster you are logged into.

Saves raw data to an output folder (outside this repo) and prints one summary line.
Only the read-only verbs get / whoami (and logs, with --logs) are used. Secret values are
never read: Secrets are listed by name and type only.

Usage:
    ocp-logging-forwarding-check.py <output-dir> [--namespace openshift-logging] [--logs 1h]
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

APIS = {
    "new": "clusterlogforwarder.observability.openshift.io",
    "old": "clusterlogforwarder.logging.openshift.io",
}
# an ACM message part looks like: "<notification|violation> - <kind> [<names>] ..."
ACM_KINDS = ("clusterlogforwarders", "clusterloggings", "logfilemetricexporters")
ACM_NAME_HINTS = ("logging", "logcollector", "kafka")


def oc(*args, check=False):
    """Run a read-only oc command; return (rc, stdout, stderr)."""
    if args[0] not in ("get", "whoami", "logs"):
        raise SystemExit(f"refusing non read-only oc command: {args[0]}")
    p = subprocess.run(["oc", *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f"oc {' '.join(args)} failed: {p.stderr.strip()}")
    return p.returncode, p.stdout, p.stderr


def oc_json(*args):
    rc, out, _ = oc(*args, "-o", "json")
    return json.loads(out) if rc == 0 and out.strip() else None


def save(outdir, name, text):
    (outdir / name).write_text(text)


def host(url):
    u = urlparse(url if "://" in url else f"x://{url}")
    return f"{u.hostname}:{u.port}" if u.port else (u.hostname or url)


def forwarders(outdir):
    """Return list of (api, item) for all ClusterLogForwarders under both API groups."""
    found = []
    for api, res in APIS.items():
        rc, out, err = oc("get", res, "-A", "-o", "yaml")
        save(outdir, f"clf-{api}-api.yaml", out if rc == 0 else f"# not available: {err.strip()}\n")
        data = oc_json("get", res, "-A")
        for item in (data or {}).get("items", []):
            found.append((api, item))
    return found


def outputs_summary(item):
    """Kafka brokers and syslog/other output endpoints from a forwarder spec (old or new API)."""
    kafka, other = set(), set()
    for o in item.get("spec", {}).get("outputs", []) or []:
        k = o.get("kafka") or {}
        for b in k.get("brokers", []) or []:
            kafka.add(host(b.strip()))
        if k.get("url"):
            kafka.add(host(k["url"]))
        if o.get("type") == "kafka" and o.get("url"):
            kafka.add(host(o["url"]))
        for t in ("syslog", "http", "splunk", "elasticsearch", "loki", "cloudwatch"):
            url = (o.get(t) or {}).get("url") or (o.get("url") if o.get("type") == t else None)
            if url:
                other.add(f"{t}:{host(url)}")
    return kafka, other


def ready(item):
    for c in item.get("status", {}).get("conditions", []) or []:
        if c.get("type") == "Ready":
            return c.get("status")
    return "?"


def operator(outdir, ns):
    rc, out, _ = oc("get", "csv", "-n", ns)
    save(outdir, "csv.txt", out)
    rc, out, _ = oc("get", "subscriptions.operators.coreos.com", "-n", ns, "-o", "yaml")
    save(outdir, "subscription.yaml", out)
    subs = (oc_json("get", "subscriptions.operators.coreos.com", "-n", ns) or {}).get("items", [])
    sub = next((s for s in subs if s.get("spec", {}).get("name") == "cluster-logging"), None)
    if not sub:
        return "-", "-"
    return sub["spec"].get("channel", "-"), sub.get("status", {}).get("installedCSV", "-")


def pods(outdir, ns):
    rc, out, _ = oc("get", "pods", "-n", ns, "-o", "wide")
    save(outdir, "pods.txt", out)
    items = (oc_json("get", "pods", "-n", ns) or {}).get("items", [])
    total = len(items)
    running = sum(1 for p in items if p.get("status", {}).get("phase") == "Running")
    restarts = max([cs.get("restartCount", 0) for p in items
                    for cs in p.get("status", {}).get("containerStatuses", []) or []] or [0])
    return running, total, restarts


def secrets(outdir, ns):
    # names and types only, never values
    rc, out, _ = oc("get", "secrets", "-n", ns, "-o",
                    "custom-columns=NAME:.metadata.name,TYPE:.type", "--no-headers")
    save(outdir, "secrets-names.txt", out)


def acm(outdir):
    """ACM policy messages on this managed cluster that mention logging objects."""
    data = oc_json("get", "policies.policy.open-cluster-management.io", "-A") or {"items": []}
    hits, bad = [], 0
    for p in data["items"]:
        for d in p.get("status", {}).get("details", []) or []:
            msg = ((d.get("history") or [{}])[0]).get("message", "")
            for part in msg.split(";"):
                part = part.strip()
                head = part.lower().split(" - ", 1)[-1]
                kind = head.split(" ", 1)[0]
                names = head[head.find("[") + 1:head.find("]")] if "[" in head else ""
                if kind in ACM_KINDS or any(h in names for h in ACM_NAME_HINTS):
                    hits.append(f"{p['metadata']['name']}\t{part}")
                    bad += part.startswith("violation")
    save(outdir, "acm-logging.txt", "\n".join(sorted(set(hits))) + "\n")
    return len(set(hits)), bad


COMPONENT = re.compile(r'component_id=([\w.-]+)')
REASON = re.compile(r'error(?:_code)?="?([^",}]+)|(Connection (?:refused|timed out)|MessageTimedOut|'
                    r'MessageSizeTooLarge|timed out|Events dropped|retries exhausted|buffer full)', re.I)
DROP = re.compile(r'dropped|discarded|retries exhausted|buffer full', re.I)
BROKER = re.compile(r'(?:ssl|sasl_ssl|plaintext|tls)://([\w.-]+:\d+)', re.I)


def collector_logs(outdir, ns, since):
    """Count the collector's own ERROR lines per output and reason. Saves counts + short samples only."""
    pods_ = (oc_json("get", "pods", "-n", ns, "-l", "app.kubernetes.io/component=collector") or {}).get("items", [])
    counts, drops, brokers, samples = Counter(), Counter(), Counter(), []
    for p in pods_:
        name = p["metadata"]["name"]
        rc, out, err = oc("logs", name, "-n", ns, f"--since={since}")
        if rc != 0:
            counts[("(log read failed)", err.strip()[:80])] += 1
            continue
        for line in out.splitlines():
            if " ERROR " not in line:
                continue
            comp = (COMPONENT.search(line) or [None, "-"])[1]
            m = REASON.search(line)
            reason = (m.group(1) or m.group(2)).strip()[:60] if m else line.split("}: ")[-1][:60]
            counts[(comp, reason)] += 1
            if DROP.search(line):
                drops[comp] += 1
            for b in BROKER.findall(line):
                brokers[b] += 1
            if counts[(comp, reason)] <= 2:  # first 2 lines of each output + reason
                samples.append(f"{name}\t{line[:400]}")
    lines = [f"{c}\t{comp}\t{reason}" for (comp, reason), c in counts.most_common()]
    save(outdir, f"collector-errors-{since}.txt",
         f"# pods={len(pods_)} since={since}\n# count\tcomponent\treason\n" + "\n".join(lines) + "\n"
         + "\n# drop-like lines per component\n" + "\n".join(f"{c}\t{k}" for k, c in drops.most_common()) + "\n"
         + "\n# brokers named in error lines (unreachable or failing)\n"
         + "\n".join(f"{c}\t{k}" for k, c in sorted(brokers.items())) + "\n")
    save(outdir, f"collector-error-samples-{since}.txt", "\n".join(samples) + "\n")
    by_comp = Counter()
    for (comp, _), c in counts.items():
        by_comp[comp] += c
    return len(pods_), by_comp, drops, sorted({b.split(":")[0] for b in brokers})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("outdir")
    ap.add_argument("--namespace", default="openshift-logging")
    ap.add_argument("--logs", metavar="SINCE", help="also count collector errors per output, e.g. --logs 1h")
    a = ap.parse_args()

    rc, server, _ = oc("whoami", "--show-server")
    if rc != 0:
        raise SystemExit("not logged in (oc whoami failed)")
    outdir = Path(a.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    save(outdir, "server.txt", server)

    clfs = forwarders(outdir)
    channel, csv = operator(outdir, a.namespace)
    running, total, restarts = pods(outdir, a.namespace)
    secrets(outdir, a.namespace)
    acm_lines, acm_bad = acm(outdir)

    parts = []
    for api, item in clfs:
        kafka, other = outputs_summary(item)
        parts.append(f"{api}-api:{item['metadata']['name']} ready={ready(item)} "
                     f"kafka=[{','.join(sorted(kafka)) or '-'}] other=[{','.join(sorted(other)) or '-'}]")
    summary = (f"forwarders={len(clfs)} | {' | '.join(parts) or 'none'} | "
               f"operator={csv} channel={channel} | pods {running}/{total} running, max restarts {restarts} | "
               f"acm logging lines={acm_lines} violations={acm_bad}")
    if a.logs:
        n_pods, by_comp, drops, bad_brokers = collector_logs(outdir, a.namespace, a.logs)
        errs = ",".join(f"{k}={v}" for k, v in by_comp.most_common()) or "none"
        drp = ",".join(f"{k}={v}" for k, v in drops.most_common()) or "none"
        if n_pods == 0:
            errs = "NO COLLECTOR PODS FOUND (label app.kubernetes.io/component=collector)"
        summary += (f" | errors {a.logs} ({n_pods} collector pods): {errs} | drop lines: {drp}"
                    f" | brokers in errors: {','.join(bad_brokers) or 'none'}")
    save(outdir, "summary.txt", summary + "\n")
    print(summary)


if __name__ == "__main__":
    sys.exit(main())
