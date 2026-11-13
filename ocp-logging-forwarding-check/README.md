# ocp-logging-forwarding-check

Read-only snapshot of OpenShift log forwarding on the cluster you are logged into.
Useful to see, cluster by cluster, which ClusterLogForwarder API is in use, where logs
go (Kafka brokers, syslog and other outputs), the logging operator version and channel,
collector pod health, and what ACM policies report for the logging objects.

## Run

```bash
oc login ...                     # or point KUBECONFIG at the cluster
./ocp-logging-forwarding-check.py <output-dir>
```

Python 3 standard library only. Write the output outside this repo: it holds live
cluster data.

## Output

| File | Content |
|---|---|
| `summary.txt` | One line, also printed |
| `clf-new-api.yaml`, `clf-old-api.yaml` | ClusterLogForwarders under `observability.openshift.io` and `logging.openshift.io` |
| `csv.txt`, `subscription.yaml` | Logging operator version and subscription |
| `pods.txt` | Pods in the logging namespace |
| `secrets-names.txt` | Secret names and types only (no values) |
| `acm-logging.txt` | ACM policy messages on this managed cluster that mention logging objects |
| `server.txt` | API server the data came from |

## Safety

- Only `oc get` and `oc whoami`; any other verb is refused in code.
- Secret values are never read.
- Both CRD groups are queried explicitly: a plain `oc get clusterlogforwarder`
  can resolve to either group when both are registered.
