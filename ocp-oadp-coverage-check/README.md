# ocp-oadp-coverage-check

Read-only report of which namespaces OADP Schedules cover, and which
VirtualMachine namespaces no active Schedule covers.

## Report

1. **Schedules**: cron, paused, included / excluded namespaces, label
   selectors, last backup. Flags all-namespace Schedules, globs, label
   selectors, and listed namespaces that do not exist.
2. **Namespaces in an OADP Schedule**: active and paused Schedules per
   namespace, with VM count.
3. **VM namespaces not in any active Schedule**: VM count and reason
   (not listed, excluded, or only in a paused Schedule).

## Coverage rules

Same as Velero:

- `includedNamespaces` empty or `*` means all namespaces.
- Entries may be globs (`app-*`).
- `excludedNamespaces` wins over `includedNamespaces`.
- A paused Schedule does not count as coverage. It is shown separately.
- A Schedule with a label selector counts as coverage but is flagged,
  because VMs without the label are skipped.

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` already logged in
- Permission to `get` Schedules, VirtualMachines, and Namespaces

Uses `oc get` and `oc whoami` only. Never reads Secrets.

## Usage

```bash
python3 ocp-oadp-coverage-check.py --server https://api.example:6443
python3 ocp-oadp-coverage-check.py --server https://api.example:6443 > coverage.md
```

The script exits before any other read if `oc whoami --show-server` is not
`--server`.

Save live output in a **private** notes repo. This directory is safe for
public repos (generic script only). Do not commit live dumps here.

## Limits

- "In a Schedule" does not mean the last backup Completed, or that a
  restore was tested.
- Label selectors are flagged, not evaluated against each VM.
- Resource-level filters (`includedResources`, `excludedResources`) are
  not checked.
