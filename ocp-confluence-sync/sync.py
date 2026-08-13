#!/usr/bin/env python3
"""
sync.py — read a value from an OpenShift ConfigMap and publish it to a
Confluence Cloud page.

Proof of concept for keeping a Confluence datasheet in sync with live
cluster state instead of manually re-scraping it.

All configuration comes from environment variables — this file is generic
and contains no site, cluster, or page identifiers:

  CONFLUENCE_EMAIL   Atlassian account email
  CONFLUENCE_TOKEN   Atlassian API token (id.atlassian.com -> Security)
  CONFLUENCE_BASE    e.g. https://<your-site>.atlassian.net
  PAGE_ID            Confluence page id to update
  CM_NAMESPACE       namespace of the source ConfigMap
  CM_NAME            ConfigMap name
  CM_KEY             data key to read

Cluster access is read-only (`oc get`). The only write is the Confluence
page update, and it is skipped when the page already shows the current
value (no version churn on scheduled runs).

Requires: python3 (stdlib only) + oc (logged in). `urllib` honours
https_proxy/no_proxy, so a proxy for Confluence does not affect oc.

Usage:
    cp env.example .env   # fill in real values -- .env is gitignored
    set -a; . ./.env; set +a
    python3 sync.py
"""

import base64
import html
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


def env(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"error: {name} not set")
    return v


EMAIL = env("CONFLUENCE_EMAIL")
TOKEN = env("CONFLUENCE_TOKEN")
BASE = env("CONFLUENCE_BASE").rstrip("/")
PAGE_ID = env("PAGE_ID")
CM_NAMESPACE = env("CM_NAMESPACE")
CM_NAME = env("CM_NAME")
CM_KEY = env("CM_KEY")

AUTH = base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode()


def confluence(method, path, payload=None):
    req = urllib.request.Request(
        BASE + path,
        method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={
            "Authorization": f"Basic {AUTH}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        sys.exit(f"error: Confluence {method} {path} -> HTTP {e.code}\n{detail}")


def read_cluster_value():
    try:
        # stdout/stderr PIPE + universal_newlines keeps this Python 3.6
        # compatible (capture_output/text need 3.7+)
        out = subprocess.run(
            ["oc", "get", "cm", CM_NAME, "-n", CM_NAMESPACE,
             "-o", f"jsonpath={{.data.{CM_KEY}}}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: oc get failed: {e.stderr.strip()}")
    value = out.stdout.strip()
    if not value:
        sys.exit(f"error: key '{CM_KEY}' empty or missing in "
                 f"{CM_NAMESPACE}/{CM_NAME}")
    return value


def build_body(value):
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    v = html.escape(value)
    return (
        "<h2>Cluster Sync Demo</h2>"
        "<table><tbody>"
        f"<tr><th>Test value</th><td><code>{v}</code></td></tr>"
        f"<tr><th>Source</th><td><code>configmap/{html.escape(CM_NAME)}</code> "
        f"in <code>{html.escape(CM_NAMESPACE)}</code>, "
        f"key <code>{html.escape(CM_KEY)}</code></td></tr>"
        f"<tr><th>Last synced</th><td>{stamp}</td></tr>"
        "</tbody></table>"
        "<p>This page is updated automatically by the confluence-sync POC "
        "script. Do not edit by hand.</p>"
    )


def main():
    value = read_cluster_value()
    print(f"cluster value: {value}")

    page = confluence(
        "GET", f"/wiki/rest/api/content/{PAGE_ID}?expand=version,body.storage")
    current_version = page["version"]["number"]
    print(f"page '{page['title']}' at version {current_version}")

    marker = f"<code>{html.escape(value)}</code>"
    if marker in page["body"]["storage"]["value"]:
        print("value unchanged -- skipping update")
        return

    confluence("PUT", f"/wiki/rest/api/content/{PAGE_ID}", {
        "id": PAGE_ID,
        "type": "page",
        "title": page["title"],
        "version": {"number": current_version + 1,
                    "message": "automated sync from cluster"},
        "body": {"storage": {"value": build_body(value),
                             "representation": "storage"}},
    })
    print(f"page updated to version {current_version + 1}")


if __name__ == "__main__":
    main()
