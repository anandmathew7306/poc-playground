# SLO Review Process

## Overview

SLO definitions live in `platform-config/slos/`. This directory documents how the team reviews and acts on SLO performance.

## Review Cadence

- **Weekly** — SRE reviews error budget burn rate per client
- **Monthly** — client-facing SLO report with trend analysis
- **Quarterly** — SLO target review with client stakeholders

## Review Checklist

- [ ] Availability SLO recording rules producing data
- [ ] Latency SLO within target for the window
- [ ] Error budget remaining > 25% for the period
- [ ] Alerting routes tested in the last 90 days
- [ ] Dashboard linked in client profile.yaml is current

## When SLO Is at Risk

1. Notify client primary contact per `contacts.yaml` escalation path
2. Open incident if error budget will be exhausted before window end
3. Document remediation plan in client documentation space
4. Review whether SLO target needs adjustment (requires client approval)

## Adding a New SLO

1. Copy `platform-config/slos/_template.yaml` to `slos/[client].yaml`
2. Define PromQL for good_events and total_events
3. Deploy PrometheusRule via GitOps
4. Verify recording rules in Prometheus UI
5. Add dashboard panel and link in client profile
