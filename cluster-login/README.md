# cluster-login

Terminal helper: pick a client, pick a cluster, then `oc login`.

Menus stay in this terminal as a boxed list. Arrow keys move, Enter selects. Clients with Prod / Non-prod groups get an environment step first.

Menus stay in this terminal as a boxed list. Arrow keys move, Enter selects. Clients with Prod / Non-prod groups get an environment step first. Empty clients still appear in the picker.

`cluster-status.sh` prints the **active** login in a yellow box (company, cluster, user, server). `cluster-logout.sh` clears all local sessions and prints the previous login in a pink box. Login confirmations use light blue. A small note reports whether Fortinet and ZeroTier look up.

## Setup

```bash
cp clusters.yaml.example clusters.yaml
# edit clusters.yaml
./cluster-login.sh
```

Or point at a file outside the repo:

```bash
export CLUSTER_LOGIN_CONFIG=~/.scripts/cluster-login.yaml
```

## Usage

```bash
cluster-login.sh
cluster-login.sh lab
cluster-login.sh lab local
cluster-login.sh list
cluster-login.sh status
cluster-login.sh --dry-run lab local
cluster-login.sh set-password lab
cluster-status.sh
cluster-logout.sh
```

Passwords live in `~/.ssh/.<client>_pass` (`chmod 600`), next to other local secret files. Not in the YAML catalog.
