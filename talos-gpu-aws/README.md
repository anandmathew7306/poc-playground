# talos-gpu-aws

AWS lab: official Talos AMI, then an NVIDIA GPU worker via Image Factory
system extensions. Goal is a pod that runs `nvidia-smi` against a real
GPU (`nvidia.com/gpu` allocatable), not just an instance that has a card.

This is independent of Cilium. GPU is an OS-level extension plus a
Kubernetes device plugin. CNI is a different layer. The local Cilium lab
is in `talos-cilium-local`.

Tested with Talos **v1.14.1**, Kubernetes **v1.37**, `g4dn.xlarge`
(Tesla T4), NVIDIA device plugin **v0.19.3**.

**Tear everything down the same day.** GPU instances cost much more than
`t3.small`. Leave nothing running.

Official notes:

- Talos on AWS: <https://docs.siderolabs.com> (Cloud Platforms → AWS)
- System extensions: <https://www.talos.dev/latest/talos-guides/configuration/system-extensions>
- Image Factory: <https://factory.talos.dev>
- NVIDIA LTS / Production split (Talos 1.8+): <https://docs.siderolabs.com/talos/v1.8/getting-started/what's-new-in-talos>

## Requirements

- AWS CLI configured for an account you control
- `talosctl` matching the AMI version
- `kubectl`
- A region with the official Sidero Labs Talos AMI
- GPU vCPU quota for the G/VT family (see below)

Do not merge this lab into `~/.kube/config`. Use a session export:

```bash
export KUBECONFIG="$PWD/kubeconfig"
```

## Phase 1 — plain Talos on EC2

Learn AWS vs Docker first. No GPU, no Cilium. Default Flannel is fine.

1. Pick a cheap type (`t3.small` is enough for one control plane).
2. Default VPC. Security group: TCP **50000** (Talos API) and TCP **6443**
   (Kubernetes API) from your IP. No SSH — Talos is API-only.
3. Find the official AMI for that region and Talos version (`talosctl image
   default --platform aws`, or query the Sidero Labs publisher account).
4. Launch with no machine config. The node comes up in maintenance mode.
5. `talosctl gen config` using the instance public IP as the endpoint.
6. `talosctl apply-config`, then `talosctl bootstrap` on the control plane.
7. Pull kubeconfig. `kubectl get nodes` should show `Ready`.

There is no `talosctl cluster create` on real infra. That command is
Docker/QEMU only. On AWS you provision the VM, apply config, and
bootstrap etcd as separate steps.

`talosctl` against a real node needs both `--nodes` and `--endpoints`,
even when they are the same address. `--nodes` is the target;
`--endpoints` is the control plane the CLI talks to.

The official AWS AMI is pre-installed on the root volume. `apply-config`
on the control plane may complete without a reboot. A worker join often
does reboot. Bare-metal ISO installs behave differently.

## Phase 2 — GPU worker, not a second control plane

Join a GPU instance as a **worker** on the Phase 1 control plane.

A single-node GPU control plane has
`node-role.kubernetes.io/control-plane:NoSchedule`. The test pod will
not schedule unless you allow workloads on the control plane. A worker
has no such taint.

Keep the Phase 1 instance running through Phase 2. Add node-to-node
rules on the security group (self-referencing):

| Port | Why |
|---|---|
| UDP 8472 | Flannel VXLAN |
| TCP 10250 | kubelet |
| TCP 50000 | Talos `apid` |
| TCP 50001 | Talos `trustd` (cert signing on join) |

If 50001 is missing, kubelet can still join while `talosctl` to the
worker fails with connection refused on 50000. Console logs show
`secrets.APIController` retrying trustd. Opening 50001 fixes it without
a reboot.

Once joined, the worker certificate lists its **private** IP, not the
public one. Talk to the worker as `--nodes <private-ip> --endpoints
<control-plane>`. Using the worker public IP as both flags fails x509.

### Image Factory schematic

As of Talos 1.8.0 the old names
`nvidia-open-gpu-kernel-modules` / `nvidia-container-toolkit` are gone.
Use the LTS or Production track. LTS is the conservative default.

`nvidia-extensions.yaml` in this folder:

```yaml
customization:
  systemExtensions:
    officialExtensions:
      - siderolabs/nvidia-open-gpu-kernel-modules-lts
      - siderolabs/nvidia-container-toolkit-lts
```

POST that to Image Factory (or pick the same pair in the web UI). The
schematic ID is a content hash of the YAML. Upgrade the worker with the
returned installer image, same Talos version as the AMI:

```bash
talosctl upgrade \
  --nodes <worker-private-ip> --endpoints <control-plane> \
  --image factory.talos.dev/installer/<schematic-id>:v1.14.1 \
  --talosconfig ./talosconfig
```

Launch the GPU node from the **same official AMI**, then upgrade in
place. That is the documented way to add extensions without building a
custom AMI.

If you interrupt `talosctl upgrade` while it is watching nodes, the
upgrade on the instance still finishes, but the client may skip
uncordon. Run `kubectl uncordon <node>` if the node stays
`SchedulingDisabled`.

Confirm extensions:

```bash
talosctl get extensions \
  --nodes <worker-private-ip> --endpoints <control-plane> \
  --talosconfig ./talosconfig
```

### Kernel modules are a separate step

Installing the extension does **not** load `nvidia.ko`. `dmesg` will
show extension services waiting for `/sys/bus/pci/drivers/nvidia`.
Patch the worker machine config (`gpu-worker-patch.yaml`):

```yaml
machine:
  kernel:
    modules:
      - name: nvidia
      - name: nvidia_uvm
      - name: nvidia_drm
      - name: nvidia_modeset
  sysctls:
    net.core.bpf_jit_harden: 1
```

```bash
talosctl patch mc \
  --patch @gpu-worker-patch.yaml \
  --nodes <worker-private-ip> --endpoints <control-plane> \
  --talosconfig ./talosconfig
```

This applies live. Afterward, `dmesg` should show the NVIDIA open kernel
module bind to the GPU, `/proc/modules` should list all four as `Live`,
and `/dev` should have `nvidia0`, `nvidiactl`, `nvidia-uvm`.

### Why not the NVIDIA GPU Operator (default mode)

The Operator’s default driver container writes kernel modules onto the
host at runtime. That fights Talos’s immutable root. Talos system
extensions are the native equivalent. Sidero’s NVIDIA docs skip the
Operator for that reason.

The Operator can still be useful later in
`driver.enabled=false, toolkit.enabled=false` mode (node labels, DCGM,
GPU Feature Discovery) on a multi-node GPU fleet. Not needed for this
lab.

### Kubernetes: RuntimeClass + device plugin

Apply `runtimeclass-nvidia.yaml`, then the official static device-plugin
manifest. Patch the DaemonSet so pods use the RuntimeClass (the stock
YAML does not set it):

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.19.3/deployments/static/nvidia-device-plugin.yml

kubectl patch daemonset nvidia-device-plugin-daemonset -n kube-system --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/runtimeClassName", "value": "nvidia"}]'
```

Check a newer device-plugin tag next time; this moves fast.

`kubectl describe node` on the GPU worker should show `nvidia.com/gpu: 1`
under Allocatable. Resources are alphabetical — give `grep` enough
context or it will cut off after `memory`.

On a larger cluster, add a `nodeSelector` or GPU taint so the plugin
does not land on non-GPU nodes.

### Proof pod

`gpu-test-pod.yaml` in this folder. Apply it, then:

```bash
kubectl logs gpu-test
```

Success is `STATUS: Completed` and a real `nvidia-smi` table (device
name, driver, CUDA, memory). A `PodSecurity` warning about missing
`securityContext` fields is non-blocking for this one-shot pod.

A recurring `ERROR: init 250 result=11` in plugin or pod logs can appear
on virtualized GPUs and still print a full table. Chase it only if a
real workload fails.

## AWS quota (do this before launch)

New accounts often have **0 vCPU** for On-Demand G and VT instances
(quota `L-DB2E81BA`). `g4dn.xlarge` then fails with `VcpuLimitExceeded`.
Request 4 vCPUs in the target region **before** Phase 2.

`CASE_CLOSED` on the quota case is not enough — denial closes the case
too. Confirm with `get-service-quota`. An approved idle quota costs
nothing.

## Teardown

Terminate the GPU instance first (it is the expensive one), then the
control plane. Wait until both are `terminated` (ENIs released). Delete
the security group. Then check:

- no leftover `available` EBS volumes (`DeleteOnTermination` should
  have removed the roots)
- no unassociated Elastic IPs (auto-assigned public IPs are not EIPs)

RuntimeClass, the device plugin, and the test pod die with the nodes.
The Image Factory schematic is not an AWS resource.

Local files (`controlplane.yaml`, `worker.yaml`, `talosconfig`,
`kubeconfig`) stay on your machine. Do not commit them. They contain
cluster secrets and addresses.

## Shell gotcha

`curl --data-binary "@~/path/file.yaml"` does not expand `~` after `@`.
Use `"@$HOME/path/file.yaml"`.

## Rollback

```bash
# replace with your instance IDs
aws ec2 terminate-instances --instance-ids <gpu-id> <control-plane-id> --region <region>
# wait until State.Name is terminated on both
aws ec2 delete-security-group --group-id <sg-id> --region <region>
```

`delete-security-group` fails with `DependencyViolation` if an ENI is
still attached. Wait and retry.
