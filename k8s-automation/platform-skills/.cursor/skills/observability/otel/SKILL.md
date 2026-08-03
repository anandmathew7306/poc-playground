---
name: observability/otel
description: >
  Use when working with OpenTelemetry collectors and instrumentation.
  Covers OTel collector deployment, traces, and metrics export.
status: stub
reviewed_at: "2026-06-13"
version: 0.1.0
layer: observability
refs:
  - core
  - observability/prometheus
---

# Observability/OTel

> **Not yet active.** PlatRel's neo stack contract requires OTel collectors on all clusters, but standardized deployment patterns and this skill are still being defined. Use `observability/prometheus` for metrics and alerts today.

## When to Use
- **Future**: OTel collector DaemonSet deployment or sidecar configuration
- **Future**: Trace export to Tempo or vendor backend
- **Now**: refer to `core` neo stack Observe Contract for requirements only

## Key Concepts (planned)
- **Collector**: OpenTelemetry Collector as DaemonSet (node-level) or sidecar (pod-level)
- **Pipelines**: receivers → processors → exporters
- **Instrumentation**: auto-instrumentation vs SDK in application repos
- **Export targets**: Prometheus (metrics), Tempo/Jaeger (traces)

## Commands and Patterns (reference)

```bash
# Planned — verify when skill goes active
oc get daemonset -n openshift-opentelemetry-operator 2>/dev/null || echo "OTel not deployed"
oc get opentelemetrycollector -A
```

## Common Issues
- N/A — skill not active. For missing telemetry, ensure Prometheus SLO rules per `observability/prometheus`.

## References
- Contract: `core` (Observe Contract section)
- Active alternative: `observability/prometheus`
