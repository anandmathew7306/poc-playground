# talos-cilium-local

Local lab: Talos Linux on the Docker provisioner, then Cilium as the CNI
(with kube-proxy replacement). Goal is to prove Cilium actually **enforces**
`NetworkPolicy`, not just that the chart installed.

Tested with Talos **v1.14.1**, Kubernetes **v1.37**, Cilium **v1.18.0**,
Docker Engine on Fedora.

Cilium is a Kubernetes-level install (Helm / DaemonSet). It is **not** baked
into the Talos image. Talos only supplies the machine config that lets Cilium
work: delete the default Flannel document, disable kube-proxy.

## Requirements

- Docker Engine running, current user in the `docker` group
- [`talosctl`](https://talos.dev/install) matching the cluster version
- Helm
- Enough RAM for 1 control plane + 1 worker (~2 GiB each)

Official install notes:

- Docker on Fedora: <https://docs.docker.com/engine/install/fedora/>
- Cilium on Talos (version-branched): <https://docs.siderolabs.com/kubernetes-guides/cni/deploying-cilium>

## Why Cilium instead of Flannel

Flannel (Talos default) is overlay pod networking only. A `NetworkPolicy`
object applies, but nothing enforces it. Cilium uses eBPF for identity-based
policy, kube-proxy replacement, Hubble, and optional encryption. That is the
reason to switch for any multi-tenant cluster.

A single-host Docker lab hides the hard CNI problems (real NICs, MTU,
cross-host routing). The Kubernetes-level Cilium values stay the same on
real machines; only the underlay changes.

## Talos v1.14 config format

Talos v1.14 moved CNI and kube-proxy settings out of the old flat
`v1alpha1` fields (`cluster.network.cni.name`, `cluster.proxy.disabled`)
into separate documents. `talosctl cluster create docker` already emits
`KubeFlannelCNIConfig` and `KubeProxyConfig`. Patching the old fields
conflicts with those documents.

`KubeProxyConfig` is control-plane only. A shared `--config-patch` that
includes it fails on workers. Use two files:

`patch-cni.yaml` (all nodes) — delete default Flannel:

```yaml
apiVersion: v1alpha1
kind: KubeFlannelCNIConfig
$patch: delete
```

`patch-proxy.yaml` (control plane only) — disable kube-proxy:

```yaml
apiVersion: v1alpha1
kind: KubeProxyConfig
enabled: false
```

Copies of both files live in this folder.

## Create the cluster

```bash
talosctl cluster create docker \
  --config-patch @patch-cni.yaml \
  --config-patch-controlplanes @patch-proxy.yaml
```

Bootstrap should print these `SKIP` lines. They mean CNI and kube-proxy
are absent on purpose, not that bootstrap failed:

```
waiting for all k8s nodes to report ready: SKIP
waiting for kube-proxy to report ready: SKIP
waiting for coredns to report ready: SKIP
```

After this, nodes are `NotReady` with `cni plugin not initialized`,
CoreDNS is `Pending`, and kube-proxy is gone. That is the expected
pre-Cilium state.

The Docker provisioner is fixed at 1 control plane. `--workers` defaults
to `1`. No extra flags are required for a 1+1 lab.

## Install Cilium

```bash
helm repo add cilium https://helm.cilium.io/
helm repo update

helm install cilium cilium/cilium \
  --version 1.18.0 \
  --namespace kube-system \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true \
  --set securityContext.capabilities.ciliumAgent="{CHOWN,KILL,NET_ADMIN,NET_RAW,IPC_LOCK,SYS_ADMIN,SYS_RESOURCE,DAC_OVERRIDE,FOWNER,SETGID,SETUID}" \
  --set securityContext.capabilities.cleanCiliumState="{NET_ADMIN,SYS_ADMIN,SYS_RESOURCE}" \
  --set cgroup.autoMount.enabled=false \
  --set cgroup.hostRoot=/sys/fs/cgroup \
  --set k8sServiceHost=localhost \
  --set k8sServicePort=7445
```

Why the non-obvious values (from the Talos Cilium guide):

| Value | Reason |
|---|---|
| Custom `securityContext.capabilities.*` | Talos does not let workloads load kernel modules, so drop `SYS_MODULE` from Cilium defaults |
| `cgroup.autoMount.enabled=false` + `cgroup.hostRoot` | Talos already mounts cgroupv2 / bpffs |
| `k8sServiceHost=localhost` + `k8sServicePort=7445` | kube-proxy is gone; point Cilium at Talos **KubePrism** |

Nodes should flip `Ready` and CoreDNS should schedule.

## Prove enforcement

```bash
kubectl create namespace netpol-test
kubectl run web --image=nginx --namespace=netpol-test --port=80 --labels=app=web
kubectl expose pod web --port=80 --namespace=netpol-test
kubectl run client --image=busybox --namespace=netpol-test --labels=app=client --command -- sleep 3600
```

Open path (no policy):

```bash
kubectl exec -n netpol-test client -- wget -qO- --timeout=3 http://web
```

Expect nginx HTML. Then apply `netpol-deny-all.yaml` and run the same
`wget`. Expect `wget: download timed out`. That is enforcement, not just
an installed CNI.

Cleanup:

```bash
kubectl delete namespace netpol-test
```

## Gotchas from this lab

- **VPN / proxy:** `curl https://talos.dev/install | sh` can fail silently
  when a VPN or proxy is up. Host DNS and image pulls fail the same way.
  Check that first.
- **Stale Docker embedded DNS:** Docker writes `127.0.0.11` into a
  container at create time and does not refresh it. A long-lived Talos
  node can sit in `ImagePullBackOff` for `quay.io` while the host and a
  fresh `busybox` container resolve fine. Recreate the cluster rather
  than debug DNS inside the old containers.
- **Old blog syntax:** many guides still show pre-1.14
  `cluster.network.cni.name`. Use the version-branched Talos Cilium page.

## Rollback

```bash
talosctl cluster destroy
```

That removes the Docker-provisioned cluster only. It does not uninstall
Docker, `talosctl`, or Helm.

## Related

GPU drivers on Talos are a different layer (Image Factory system
extensions + a kernel-module machine-config patch). See `talos-gpu-aws`.
