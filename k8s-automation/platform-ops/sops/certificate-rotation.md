---
title: "Certificate Rotation"
type: "sop"
platform: "ocp | rosa | rosa-hcp | eks"
last_updated: "2026-06-13"
author: "platrel"
---

# Certificate Rotation SOP

Procedure for rotating cluster certificates before expiry. Covers API server, ingress, service serving certificates, and webhook certificates on OCP/ROSA clusters. EKS certificates are managed by AWS but IRSA/OIDC certificates are included.

## Prerequisites

- [ ] Certificate expiry identified (alert `CertificateExpirySoon` or manual audit)
- [ ] Maintenance window scheduled if rotation causes brief disruption
- [ ] Change ticket approved
- [ ] Cluster health check passed
- [ ] Rollback plan: previous CA bundle retained for 30 days

## Certificate Inventory

```bash
# List all certificates and expiry dates (OCP)
oc get certificates -A
oc get secret -A -o json | jq -r '.items[] | select(.type=="kubernetes.io/tls") | "\(.metadata.namespace)/\(.metadata.name)"'

# Check API server certificate expiry
echo | openssl s_client -connect api.<cluster-domain>:6443 2>/dev/null | openssl x509 -noout -dates

# Check ingress certificate expiry
echo | openssl s_client -connect apps.<cluster-domain>:443 -servername <app-route> 2>/dev/null | openssl x509 -noout -dates

# Check cluster certificate authority
oc get configmap kube-root-ca.crt -n kube-system -o jsonpath='{.data.ca\.crt}' | openssl x509 -noout -dates
```

Record all certificates expiring within 30 days in the change ticket.

## Rotation Steps — API Server Certificate (OCP/ROSA)

OCP automatically rotates API server certificates via the `kube-apiserver-operator`. Manual intervention is rarely needed.

```bash
# Verify API server operator health
oc get clusteroperator kube-apiserver
oc get kubeapiserver cluster -o yaml | grep -A10 conditions

# Check current serving certificate secret
oc get secret kube-apiserver-lb-server-cert -n openshift-kube-apiserver-operator -o yaml

# Force rotation if operator is stuck (maintenance window required)
oc annotate kubeapiserver cluster -n openshift-kube-apiserver-operator \
  cert rotation-required=true --overwrite

# Monitor rotation
oc get pods -n openshift-kube-apiserver -w
oc logs -n openshift-kube-apiserver-operator deployment/kube-apiserver-operator --tail=50

# Verify new certificate dates
echo | openssl s_client -connect api.<cluster-domain>:6443 2>/dev/null | openssl x509 -noout -dates
```

## Rotation Steps — Ingress / Router Certificate

```bash
# Check current router certificate
oc get secret router-certs -n openshift-ingress -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -dates

# Option A: Let cert-manager auto-renew (if configured)
oc get certificate -n openshift-ingress
oc describe certificate <cert-name> -n openshift-ingress

# Option B: Manual replacement with new cert from CA
oc create secret tls router-certs-new \
  --cert=<new-cert.pem> --key=<new-key.pem> -n openshift-ingress

# Update ingress controller to use new cert
oc patch ingresscontroller default -n openshift-ingress-operator --type=merge \
  -p '{"spec":{"defaultCertificate":{"name":"router-certs-new"}}}'

# Verify router pods reload
oc get pods -n openshift-ingress -w

# Test HTTPS endpoint
curl -v https://<app-route>/healthz
```

## Rotation Steps — Service Serving Certificates

```bash
# Check service-ca operator
oc get clusteroperator service-ca
oc get secret signer-secret -n openshift-service-ca -o yaml

# Service serving certs auto-rotate — verify operator is healthy
oc logs -n openshift-service-ca deployment/service-ca-operator --tail=50

# If specific service cert expired, delete secret to trigger re-issue
oc delete secret <service-serving-cert> -n <namespace>
# Pod restart may be required to pick up new cert
oc rollout restart deployment/<deployment> -n <namespace>
```

## Rotation Steps — Webhook Certificates

```bash
# Identify webhook certificate secrets
oc get validatingwebhookconfigurations -o json | jq -r '.items[].metadata.name'
oc get mutatingwebhookconfigurations -o json | jq -r '.items[].metadata.name'

# Check operator managing the webhook cert (e.g., cert-manager, service-ca)
oc get clusteroperator | grep -iE 'cert|webhook'

# Restart operator to force cert regeneration
oc rollout restart deployment/<webhook-operator> -n <operator-namespace>

# Verify webhook is functional
oc apply -f <test-resource.yaml>  # should succeed without webhook errors
```

## Rotation Steps — ROSA HCP Hosted Cluster Certificates

```bash
# Hosted cluster certs managed by Hypershift — check HostedCluster status
oc get hostedcluster <cluster-name> -n clusters-<name> -o yaml | grep -A10 conditions

# Control plane certs rotate automatically during upgrades
# For manual intervention, escalate to Red Hat support

# Worker node kubelet certs — rotate via NodePool rollout
oc get nodepool <nodepool-name> -n clusters-<name>
```

## Rotation Steps — EKS OIDC / IRSA

```bash
# EKS API server cert is AWS-managed — no action needed
# IRSA: verify OIDC provider thumbprint if using custom CA
aws eks describe-cluster --name <cluster> --query 'cluster.certificateAuthority'
aws iam list-open-id-connect-providers

# Update thumbprint if IdP CA changed
aws iam update-open-id-connect-provider-thumbprint \
  --open-id-connect-provider-arn <arn> --thumbprint-list <new-thumbprint>
```

## Post-Rotation Validation

```bash
# All operators healthy
oc get clusteroperators | grep -i false

# API server responsive
oc get --raw /healthz

# Ingress serving valid cert
curl -v https://<app-route>/healthz 2>&1 | grep "expire date"

# No webhook errors in API server logs
oc logs -n openshift-kube-apiserver-operator deployment/kube-apiserver-operator --tail=30 | grep -i webhook

# Run platform health check
# client: <name> | task: platform-health-check
```

## Rollback

```bash
# Ingress: revert to previous certificate secret
oc patch ingresscontroller default -n openshift-ingress-operator --type=merge \
  -p '{"spec":{"defaultCertificate":{"name":"router-certs"}}}'

# API server: operator-managed — rollback not supported, escalate
# Webhook: restart operator with previous config from GitOps
```

## Sign-Off

| Step | Engineer | Date | Ticket |
|------|----------|------|--------|
| Inventory complete | | | |
| Rotation executed | | | |
| Validation passed | | | |
| Monitoring confirmed (no expiry alerts) | | | |

## Related

- Skill: platform/ocp
- Skill: troubleshooting/ocp-operators
- Runbook: runbooks/ocp/operator-degraded.md
- SOP: sops/cluster-upgrade.md
- SOP: sops/access-provisioning.md

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-13 | platrel | Complete cluster certificate rotation procedure |
