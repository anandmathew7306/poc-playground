#!/usr/bin/env bash
# Create the single-node OpenShift VM on Proxmox. Run on the Proxmox host.
# Does not start the VM: check `qm config $VMID` first, then `qm start $VMID`.
set -euo pipefail

VMID=900                      # a free VM ID
NAME=sno-poc
CORES=16                      # minimum 8
MEMORY_MB=65536               # minimum 16384
STORAGE=local-lvm             # storage for the disks
OS_DISK_GB=120                # OpenShift itself
DATA_DISK_GB=100              # left empty for LVM Storage
BRIDGE=vmbr0
MAC=BC:24:11:00:00:20         # must match the MAC entered in the Assisted Installer
ISO=local:iso/sno-discovery.iso

qm create "$VMID" --name "$NAME" --ostype l26 --machine q35 \
  --cpu host --sockets 1 --cores "$CORES" --memory "$MEMORY_MB" --balloon 0 \
  --scsihw virtio-scsi-single \
  --scsi0 "$STORAGE:$OS_DISK_GB,ssd=1,discard=on,iothread=1" \
  --scsi1 "$STORAGE:$DATA_DISK_GB,ssd=1,discard=on,iothread=1" \
  --net0 "virtio=$MAC,bridge=$BRIDGE" \
  --ide2 "$ISO,media=cdrom" \
  --boot 'order=scsi0;ide2'

echo "Created VM $VMID. Check: qm config $VMID"
