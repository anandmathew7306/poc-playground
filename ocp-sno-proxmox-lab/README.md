# Single-node OpenShift on Proxmox (Assisted Installer)

A small lab cluster for trying things out: one VM, built from the Red Hat Hybrid Cloud Console with the Assisted Installer, static IP, local DNS, and access from a laptop through an SSH SOCKS proxy.

Tested with OpenShift 4.20 on Proxmox VE 8.4.

## What you need

| Item | Example used here |
|---|---|
| Proxmox host with free capacity | 16 vCPU, 64 GB RAM, ~220 GB thin storage |
| Lab network (bridge) with internet access | `vmbr0`, `192.0.2.0/24`, gateway `192.0.2.1` |
| A free static IP for the node | `192.0.2.20` |
| A DNS server you control on the lab network | bind9 on a jump host, `192.0.2.9` |
| Cluster name / base domain | `poc` / `example.lab` |
| Red Hat account (trial is fine) | console.redhat.com |

Sizing: 8 vCPU / 16 GB / 120 GB is the single-node minimum. 16 vCPU / 64 GB leaves room for operators such as OADP or OpenShift Virtualization. A second empty disk is used by LVM Storage for app volumes and snapshots.

Avoid `.local` as base domain: many systems send `*.local` to mDNS instead of DNS.

## 1. DNS

The installer checks these names. On a single node they all point to the node IP.

```
api.poc.example.lab       -> 192.0.2.20
api-int.poc.example.lab   -> 192.0.2.20
*.apps.poc.example.lab    -> 192.0.2.20
```

With bind9: append [`bind/named.conf.local.snippet`](bind/named.conf.local.snippet) to `/etc/bind/named.conf.local`, copy [`bind/db.example.lab`](bind/db.example.lab) to `/etc/bind/`, then:

```bash
sudo named-checkconf && sudo named-checkzone example.lab /etc/bind/db.example.lab
sudo rndc reload
dig @192.0.2.9 +short api.poc.example.lab test.apps.poc.example.lab   # both: 192.0.2.20
```

Back up `named.conf.local` first. Raise the zone serial on every change.

## 2. Hybrid Cloud Console

console.redhat.com → OpenShift → Create cluster → Datacenter → **Assisted Installer → Create cluster**.

| Page | Setting |
|---|---|
| Cluster details | Name `poc`, base domain `example.lab`, version (plain, not `-multi`), x86_64, control plane nodes **1 (SNO)**, network **Static IP**, disk encryption off |
| Static network | IPv4, no VLAN (if the bridge is untagged). DNS: **only your lab DNS** (a public resolver as second entry can answer "not found" for the cluster names). Subnet and gateway of the bridge. |
| Host specific | MAC address + IP. **Choose the MAC yourself now** (e.g. `BC:24:11:00:00:20`, `BC:24:11` is the Proxmox prefix) and give the VM the same MAC later. |
| Operators | **Logical Volume Manager Storage** (gives a StorageClass and a VolumeSnapshotClass). Add others later from OperatorHub if needed. |
| Add host | **Full image file** (no download at boot), paste an SSH public key, generate, copy the download URL. |

## 3. Proxmox VM

Download the ISO straight onto Proxmox, then create the VM: [`proxmox/create-vm.sh`](proxmox/create-vm.sh).

```bash
wget -O /var/lib/vz/template/iso/sno-discovery.iso '<ISO URL>'
grep -il 'BC:24:11:00:00:20' /etc/pve/qemu-server/*.conf   # no output = MAC free
bash create-vm.sh   # edit the variables at the top first
qm config <VMID>    # check MAC, cores, memory, disks, boot order
qm start <VMID>
```

Notes:
- `--cpu host` is required. `--balloon 0` keeps RAM fixed.
- Boot order disk first, then CD: the empty disk falls through to the ISO; after the install it boots from disk.
- On a thin pool, Proxmox may warn that the sum of thin volumes exceeds the pool. Only written data uses space; keep an eye on `lvs` Data%.

## 4. Install

1. The host shows up in the console within a few minutes. All checks should be green.
2. **Check the installation disk.** The installer may pick the smaller (second) disk. Set the larger one as *Installation disk*. The second disk stays empty for LVM Storage; its *Format* box can be greyed out on a brand-new disk, which is fine.
3. Optional: rename the host (the default name is its MAC).
4. Networking: user-managed (fixed for SNO), machine network = your subnet. Defaults for pod/service networks are fine if they do not overlap your lab.
5. Install. About 45–60 minutes, one automatic reboot.
6. Save the kubeadmin password in a password manager. The downloadable kubeconfig holds a permanent admin certificate: keep it private (`chmod 600`) or do not keep it.

## 5. Access from a laptop

If the laptop only reaches a jump host on the lab network (VPN, overlay network), open a SOCKS proxy through it:

```bash
ssh -N -D 1081 user@<jump-host>
export HTTPS_PROXY=socks5://127.0.0.1:1081 NO_PROXY=localhost,127.0.0.1
oc login https://api.poc.example.lab:6443 -u kubeadmin --insecure-skip-tls-verify
```

Things that tripped us up:

| Symptom | Cause | Fix |
|---|---|---|
| `lookup api.poc.example.lab: no such host` | `HTTPS_PROXY` not set in *this* shell, so `oc` resolves locally | Export it in the shell you use |
| Proxy works but names do not resolve | Over SOCKS, names are resolved **on the jump host**. Its own resolver did not know the lab zone (here it pointed to a dead server) | Point the jump host at the lab DNS (e.g. its own bind9 on `127.0.0.1`). Back up `/etc/resolv.conf` first |
| `aws: Failed to connect to proxy URL "http://socks5://…"` | The AWS CLI cannot use a SOCKS proxy | Run it without the proxy: `env -u HTTPS_PROXY aws …` |
| Browser cannot open the console | Browser not using the proxy, or resolving locally | Proxy extension (e.g. FoxyProxy) for `*example.lab`, with **proxy DNS** on |

## 6. After the install

```bash
oc get nodes                                   # Ready
oc get sc,volumesnapshotclass                  # lvms-vg1 for both
oc patch storageclass lvms-vg1 -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

`WaitForFirstConsumer` on the StorageClass means a new PVC stays *Pending* until a pod uses it. That is normal.

## Files

| File | What |
|---|---|
| `bind/named.conf.local.snippet` | Zone declaration to append |
| `bind/db.example.lab` | Zone file with the three cluster records |
| `proxmox/create-vm.sh` | `qm create` for the SNO VM, variables at the top |
