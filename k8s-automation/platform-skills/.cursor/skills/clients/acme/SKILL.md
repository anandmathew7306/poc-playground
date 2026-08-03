---
name: acme-client
description: >
  Use when working on any task for client Acme Corporation.
  Loads Acme-specific terminology, compliance requirements (SOC2),
  documentation style (Confluence), and active skill set.
  Always load this before any task skill when client is acme.
status: active
reviewed_at: "2026-06-01"
version: 1.0.0
layer: clients
refs:
  - core
  - platform/rosa-hcp
  - cloud/aws
  - deploy/kustomize
  - acm/policies
  - observability/prometheus
---

# Acme Client Overlay

## Profile
Load from: platform-config/clients/acme/profile.yaml

## Platform Context
- Platform: ROSA with Hosted Control Planes (Hypershift)
- Cloud: AWS eu-west-1 (prod), eu-west-2 (dr)
- Deploy tool: Kustomize
- ACM hub cluster: hub-prod (separate cluster)

## Compliance Context
- SOC2 Type II in scope
- All changes require audit log entry
- No direct cluster access without ticket reference
- Data classification: confidential — no client data in logs or error messages

## Terminology
| Generic term | Acme term |
|--------------|-----------|
| production | production (never "prod" in client-facing docs) |
| nonprod | staging |
| cluster upgrade | platform maintenance window |
| incident | service event |

## Documentation Style
- Tool: Confluence
- Space: https://acme.atlassian.net/wiki/spaces/PLATFORM
- Format: every runbook page must have: Summary, Steps, Rollback, Sign-off table
- Tone: formal, no jargon in executive summaries

## Escalation
- P1: page PagerDuty immediately, notify jane.smith@acme.example.com within 15 min
- All changes to production require ACME-prefixed ticket reference

## Contacts
See: platform-config/clusters/acme-prod/contacts.yaml
