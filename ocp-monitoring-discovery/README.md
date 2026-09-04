# ocp-monitoring-discovery

Read-only **inventory** of the OpenShift monitoring stack (Cluster Monitoring
Operator, user-workload monitoring, related CRDs, scrape/rule counts).

## Requirements

- `python3` (stdlib only, no pip packages)
- `oc` logged in to the target cluster
- Permission to `get`/`list` the objects below

**Read-only:** `oc get` / `oc whoami` only. Never apply/patch/delete.
**Never reads Secrets** (no Alertmanager routing dump).

## Usage

```bash
python3 ocp-monitoring-discovery.py
python3 ocp-monitoring-discovery.py > inventory.md
```

Save live output (hostnames, counts, ConfigMap knobs) in a **private** notes
repo. This directory is safe for public repos (generic script only).

## What it prints

| Section | Source |
|---|---|
| A identity | `whoami`, ClusterVersion, Infrastructure |
| B operators | `co monitoring`; OLM Subscriptions matching monitoring-ish names |
| C namespaces | names matching monitor / prometheus / grafana / netobserv / … |
| D CRDs | monitoring / grafana / netobserv / ACM observability types (not ClusterLogForwarder) |
| E instances + counts | Prometheus, Alertmanager, ThanosRuler, ServiceMonitor, … |
| F config + pods + routes | `cluster-monitoring-config` and UWM ConfigMaps (credential-shaped keys stripped) |
| Rules / scrapes rollup | PrometheusRule alert counts by namespace; ServiceMonitor by namespace; PodMonitor names |

## Related

Logging / SIEM is a different inventory. Alertmanager webhook/email config is
a Secret — inspect that by hand if the inventory shows a custom CMO stack.
