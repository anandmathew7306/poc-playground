# Platform Matrix

PlatRel operates multi-cloud Kubernetes platforms for client workloads. This matrix is the source of truth for which platforms and clouds are in scope, their status, and which skills apply.

## Team

| Field | Value |
|-------|-------|
| Team | PlatRel (Platform Reliability) |
| Primary cloud | AWS (active) |
| Secondary cloud | Azure (stub — not yet active) |
| GitOps repos | platform-skills, platform-config, platform-ops |

## Platforms

| Platform | Status | Cloud(s) | CLI | Primary skill | Notes |
|----------|--------|----------|-----|---------------|-------|
| OCP | Active | AWS, on-prem | `oc` | `platform/ocp` | Self-managed OpenShift 4.14+; full operator stack |
| ROSA | Active | AWS | `oc` | `platform/rosa` | Red Hat managed OpenShift; STS/IAM auth |
| ROSA HCP | Active | AWS | `oc` | `platform/rosa-hcp` | Hypershift hosted control planes; primary for new clients |
| EKS | Active | AWS | `kubectl` + `aws` | `platform/eks` | Managed Kubernetes; AWS-native add-ons |

## Cloud Providers

| Cloud | Status | Skill | Regions in use | Notes |
|-------|--------|-------|----------------|-------|
| AWS | Active | `cloud/aws` | eu-west-1, eu-west-2, us-east-1 | IAM, STS, VPC, EBS CSI, ALB controller |
| Azure | Stub | `cloud/azure` | — | Planned for AKS workloads; skill is placeholder only |
| On-prem | Limited | — | Internal DC | OCP dev/test clusters only |

## Skill Composition by Layer

| Layer | Skills | Purpose |
|-------|--------|---------|
| Core | `core` | Team standards, naming, security gates |
| Platform | `platform/ocp`, `platform/rosa`, `platform/rosa-hcp`, `platform/eks` | Cluster-specific operations |
| Cloud | `cloud/aws`, `cloud/azure` (stub) | Cloud provider CLI and IAM |
| Deploy | `deploy/kustomize` | Kustomize base+overlay GitOps |
| ACM | `acm/policies`, `acm/placement` | RHACM policy and placement |
| Observability | `observability/prometheus`, `observability/platform-health`, `observability/otel` (stub), `observability/logging` (stub) | Metrics, health, traces, logs |
| Troubleshooting | `troubleshooting/ocp-nodes`, `troubleshooting/ocp-operators`, `troubleshooting/acm-policies`, `troubleshooting/network` | Incident diagnostics |
| Tasks | `tasks/client-onboarding`, `tasks/incident-response`, `tasks/platform-health-check`, `tasks/policy-authoring` | End-to-end workflows |

## Client → Platform Mapping

Resolve from `platform-config/clients/[client]/profile.yaml`:

| Client (example) | Platform | Cloud | Deploy | ACM |
|------------------|----------|-------|--------|-----|
| acme | rosa-hcp | aws | kustomize | managed |

## When to Use Which Platform Skill

- **OCP**: Self-managed clusters, MCO upgrades, full operator lifecycle, on-prem
- **ROSA**: Classic ROSA (non-HCP), STS credential issues, managed add-ons
- **ROSA HCP**: HostedCluster, NodePool, Hypershift operator on management cluster
- **EKS**: `kubectl` workflows, EKS add-ons, node groups, IRSA

## Related

- Onboarding: `docs/onboarding-bootcamp.md`
- Standards: `.cursor/skills/core/SKILL.md`
- Runbooks: `platform-ops/runbooks/`
