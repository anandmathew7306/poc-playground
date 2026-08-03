# platform-ops

Operational knowledge layer for the PlatRel platform team. Contains runbooks, postmortems, standard operating procedures (SOPs), incident lifecycle documentation, and SLO review processes. If it helps an engineer respond to an incident, it lives here.

This repo is one of three platform repositories:

| Repo | Purpose |
|------|---------|
| **platform-skills** | AI skill library — teaches the Cursor agent how the team works |
| **platform-config** | IaC — cluster configs, RHACM policies, Kustomize bases, client profiles |
| **platform-ops** | Runbooks, SOPs, postmortems — operational knowledge (this repo) |

## Directory Structure

```
platform-ops/
├── runbooks/           # Alert-driven troubleshooting guides
│   ├── _template.md    # Runbook format — copy for new runbooks
│   ├── ocp/            # OpenShift Container Platform
│   ├── rosa/           # Red Hat OpenShift on AWS (classic)
│   ├── rosa-hcp/       # ROSA with Hosted Control Planes
│   ├── eks/            # Amazon EKS
│   ├── acm/            # Red Hat Advanced Cluster Management
│   ├── observability/  # Prometheus, Alertmanager, scrape targets
│   └── network/        # OVN, DNS, egress IP
├── sops/               # Standard operating procedures (planned work)
│   ├── cluster-upgrade.md
│   ├── client-offboarding.md
│   ├── access-provisioning.md
│   └── certificate-rotation.md
├── postmortems/        # Blameless incident reviews
├── incidents/          # Incident lifecycle documentation
└── slos/               # SLO review process
```

## How Runbooks Link to platform-skills

Runbooks and skills are complementary — neither duplicates the other.

| Layer | Repo | Role |
|-------|------|------|
| **Skills** | platform-skills | Teach the agent *how* to work — commands, patterns, platform context, client terminology |
| **Runbooks** | platform-ops | Tell the engineer *what to do* during a specific alert or failure mode |

### Resolution Chain

When an incident occurs, the agent follows this chain (defined in `core` skill):

1. **Task skill** loads — e.g., `tasks/incident-response`
2. **Client profile** resolves from `platform-config/clients/<client>/profile.yaml`
3. **Platform skill** activates — e.g., `platform/rosa-hcp` for Acme
4. **Troubleshooting skill** provides diagnostic patterns — e.g., `troubleshooting/ocp-nodes`
5. **Runbook** provides step-by-step remediation — e.g., `runbooks/rosa-hcp/nodepool-unavailable.md`

### Cross-Reference Map

| Runbook Category | Primary Skill(s) | Troubleshooting Skill |
|-----------------|------------------|----------------------|
| `runbooks/ocp/` | `platform/ocp` | `troubleshooting/ocp-nodes`, `troubleshooting/ocp-operators` |
| `runbooks/rosa/` | `platform/rosa`, `cloud/aws` | `troubleshooting/ocp-operators` |
| `runbooks/rosa-hcp/` | `platform/rosa-hcp`, `cloud/aws` | — |
| `runbooks/eks/` | `platform/eks`, `cloud/aws` | — |
| `runbooks/acm/` | `acm/policies`, `acm/placement` | `troubleshooting/acm-policies` |
| `runbooks/observability/` | `observability/prometheus` | `observability/platform-health` |
| `runbooks/network/` | `platform/ocp` | `troubleshooting/network` |

Every runbook's **Related** section lists the skills and sibling runbooks to load next.

### Client Profile Integration

Client profiles in `platform-config` reference this repo:

```yaml
# platform-config/clients/acme/profile.yaml
spec:
  docs:
    runbook_path: platform-ops/runbooks/
```

The `tasks/incident-response` skill uses `runbook_path` to resolve the correct runbook for a given alert. The `tasks/client-onboarding` skill creates a runbook index linking to relevant entries.

## Using Runbooks

### During an Incident

```
client: acme | task: incident-response | alert: NodePoolUnavailable
```

The agent will:
1. Load `clients/acme` skill for terminology and escalation paths
2. Load `platform/rosa-hcp` for platform commands
3. Open `runbooks/rosa-hcp/nodepool-unavailable.md` for remediation steps

### Creating a New Runbook

1. Copy `runbooks/_template.md` to the appropriate platform subdirectory
2. Fill every section — no placeholders in merged runbooks
3. Add **Related** links to skills and sibling runbooks
4. Add a Change Log entry with date and author
5. Open PR — runbooks require review per CONSTITUTION Law 3

### After an Incident (Required)

Within 48 hours of closing an incident:
- [ ] Runbook exists or is updated in this repo
- [ ] If the agent lacked context, a skill is updated in platform-skills
- [ ] If config was wrong, a PR is open in platform-config
- [ ] Postmortem filed in `postmortems/` for P1/P2 incidents

## SOPs vs Runbooks

| Type | When to Use | Location |
|------|-------------|----------|
| **Runbook** | Reactive — alert fired, something is broken | `runbooks/` |
| **SOP** | Proactive — planned maintenance or process | `sops/` |

SOPs cover: cluster upgrades, client offboarding, access provisioning, certificate rotation.

## Runbook Index

### OpenShift (OCP)
- [Node NotReady](runbooks/ocp/node-notready.md)
- [Operator Degraded](runbooks/ocp/operator-degraded.md)
- [MCO Stuck](runbooks/ocp/mco-stuck.md)
- [etcd Unhealthy](runbooks/ocp/etcd-unhealthy.md)

### ROSA
- [STS Auth Failure](runbooks/rosa/sts-auth-failure.md)
- [Managed Add-on Degraded](runbooks/rosa/managed-addon-degraded.md)

### ROSA HCP
- [HostedCluster Degraded](runbooks/rosa-hcp/hostedcluster-degraded.md)
- [NodePool Unavailable](runbooks/rosa-hcp/nodepool-unavailable.md)

### EKS
- [Node NotReady](runbooks/eks/node-notready.md)
- [Add-on Degraded](runbooks/eks/addon-degraded.md)

### ACM
- [Policy Non-Compliant](runbooks/acm/policy-noncompliant.md)
- [Placement Not Matching](runbooks/acm/placement-not-matching.md)
- [Hub Degraded](runbooks/acm/hub-degraded.md)

### Observability
- [Prometheus Down](runbooks/observability/prometheus-down.md)
- [Alertmanager Silenced](runbooks/observability/alertmanager-silenced.md)
- [Scrape Target Down](runbooks/observability/scrape-target-down.md)

### Network
- [OVN Pod Connectivity](runbooks/network/ovn-pod-connectivity.md)
- [DNS Resolution Failure](runbooks/network/dns-resolution-failure.md)
- [Egress IP Not Working](runbooks/network/egress-ip-not-working.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODEOWNERS](CODEOWNERS). All runbook changes require PR review. Follow conventional commits (`docs:`, `feat:`).

## Related Repositories

- [platform-skills](../platform-skills/) — skill library consumed via git submodule
- [platform-config](../platform-config/) — client profiles, cluster info, IaC
- [docs/ACTION_PLAN.md](../docs/ACTION_PLAN.md) — full platform bootstrap plan
