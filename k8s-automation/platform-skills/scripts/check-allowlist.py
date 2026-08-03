#!/usr/bin/env python3
"""Verify no external URLs in skills outside the approved allowlist."""
import re
import sys
from pathlib import Path

ALLOWED_DOMAINS = {
    "github.com",
    "docs.openshift.com",
    "access.redhat.com",
    "grafana.example.com",
    "acme.atlassian.net",
    "pagerduty.example.com",
    "platform.io",
}

URL_PATTERN = re.compile(r"https?://([a-zA-Z0-9.-]+)")

def check_file(path: Path) -> list[str]:
    errors = []
    content = path.read_text()
    for match in URL_PATTERN.finditer(content):
        domain = match.group(1)
        if domain not in ALLOWED_DOMAINS:
            errors.append(f"{path}: unapproved URL domain '{domain}'")
    return errors

def main():
    base = Path(".cursor/skills")
    errors = []
    for skill_file in base.rglob("SKILL.md"):
        errors.extend(check_file(skill_file))
    if errors:
        for e in errors:
            print(f"FAIL {e}")
        sys.exit(1)
    print("OK   all URLs within allowlist")

if __name__ == "__main__":
    main()
