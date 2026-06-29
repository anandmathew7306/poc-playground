# Openshift Network Report

A read-only script that generates a network reference report for an OpenShift cluster — one command instead of hunting through docs or running many `oc` commands by hand.

## What it does

Connects to whatever cluster you're currently logged into (`oc`) and prints a Markdown report covering:

- **Node Inventory** — hostname, role, IPv4/IPv6
- **Physical NIC Inventory** — interface, MAC, bond/bridge, MTU, state
- **Bond Detail** — mode, LACP rate, miimon, members
- **VLAN & Interface Summary** — VLAN ID, parent, addresses, MTU
- **VRF & Routing** — VRF, routing table ID, gateway
- **BGP Peers** — peer address, ASNs, VRF, BFD
- **IP Address Pools** — addresses, autoAssign, avoidBuggyIPs
- **BGP Advertisements** — pools, peers, aggregation length, localPref
- **LoadBalancer Services** — namespace, service, external IP

Data comes from the Kubernetes API, NodeNetworkState (NNS), and MetalLB resources. It is **read-only** — only `oc get` / `oc whoami` are used; nothing is modified.

## Requirements

- `python3` (no pip packages needed)
- `oc`, logged in to the target cluster

## Usage

```bash
python3 ocp-net-report.py                 # print report to screen
python3 ocp-net-report.py > report.md     # save to a file
python3 ocp-net-report.py --all-nics      # include down/unused NICs and the geneve device
```

## Note

The **output** contains live cluster values (IPs, hostnames). Do not commit generated reports — only the script. The included `.gitignore` excludes report files.