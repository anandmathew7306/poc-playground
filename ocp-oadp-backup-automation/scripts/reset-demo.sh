#!/usr/bin/env bash
# Reset the demo to "nothing backed up", so the label flow can be shown or practised again.
#
# Removes:  backup=... labels on namespaces, the automation's Schedules and Backups,
#           Velero's kopia repository records, finished DataUploads / DeleteBackupRequests,
#           and everything under s3://<bucket>/<prefix>/.
# Keeps:    OADP, the BSL, the automation (CronJob, RBAC, settings), demo-app and its data.
#
# Needs: oc logged in to the test cluster, aws CLI logged in. Run from your own terminal.
# Usage: API_SERVER=https://api.<cluster>.<domain>:6443 BUCKET=<bucket> [PREFIX=velero] ./reset-demo.sh
set -euo pipefail

API_SERVER="${API_SERVER:?set API_SERVER to the test cluster API URL}"
NS=openshift-adp
BUCKET="${BUCKET:?set BUCKET to the backup bucket}"
PREFIX="${PREFIX:-velero}"
MANAGED="app.kubernetes.io/managed-by=label-scheduler"
awsx() { env -u HTTPS_PROXY -u https_proxy aws "$@"; }   # AWS CLI cannot use the lab SOCKS proxy

# --- Safety: expected cluster and AWS login only ---------------------------------
server=$(oc whoami --show-server 2>/dev/null || true)
if [[ "$server" != "$API_SERVER" ]]; then
  echo "Logged in to ${server:-nothing}, expected $API_SERVER. Stopping."; exit 1
fi
if ! awsx sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS CLI not logged in. Run: env -u HTTPS_PROXY aws login"; exit 1
fi

# --- Show what will be removed ----------------------------------------------
labelled=$(oc get namespaces -l backup -o jsonpath='{range .items[*]}{.metadata.name}{" "}{end}')
schedules=$(oc get schedules -n "$NS" -l "$MANAGED" -o name | sed 's|.*/||' | tr '\n' ' ')
backups=$(oc get backups -n "$NS" -l "$MANAGED" -o name | sed 's|.*/||' | tr '\n' ' ')
objects=$(awsx s3 ls "s3://$BUCKET/$PREFIX/" --recursive | wc -l)

echo "Cluster : $server"
echo "Remove label backup from : ${labelled:-none}"
echo "Delete Schedules         : ${schedules:-none}"
echo "Delete Backups           : ${backups:-none}"
echo "Delete S3 objects        : $objects under s3://$BUCKET/$PREFIX/"
read -r -p "Proceed? [y/N] " ans
[[ "$ans" == y || "$ans" == Y ]] || { echo "Nothing changed."; exit 0; }

# 1. Remove labels first, so the CronJob does not recreate Schedules
if [[ -n "$labelled" ]]; then
  oc label namespace $labelled backup-
fi

# 2. Delete the automation's Schedules (only those it created)
oc delete schedules -n "$NS" -l "$MANAGED" --ignore-not-found

# 3. Delete Backups the Velero way (also removes their files in S3)
for b in $backups; do
  oc create -n "$NS" -f - >/dev/null <<EOF
apiVersion: velero.io/v1
kind: DeleteBackupRequest
metadata:
  generateName: reset-${b:0:40}-
spec:
  backupName: $b
EOF
  echo "delete requested: $b"
done

# 4. Wait for Velero to finish deleting (max ~3 min)
for i in $(seq 1 36); do
  left=$(oc get backups -n "$NS" -l "$MANAGED" --no-headers 2>/dev/null | wc -l)
  [[ "$left" -eq 0 ]] && break
  echo "waiting for $left backup(s) to be deleted..."; sleep 5
done
left=$(oc get backups -n "$NS" -l "$MANAGED" --no-headers 2>/dev/null | wc -l)
if [[ "$left" -ne 0 ]]; then
  echo "Backups still present after 3 min. Check: oc get deletebackuprequests -n $NS"; exit 1
fi

# 5. Clear leftovers: kopia repo records, finished DataUploads and delete requests
oc delete backuprepositories -n "$NS" --all --ignore-not-found
oc delete datauploads -n "$NS" --all --ignore-not-found
oc delete deletebackuprequests -n "$NS" --all --ignore-not-found

# 6. Empty the bucket prefix (kopia data is not removed by step 3)
awsx s3 rm "s3://$BUCKET/$PREFIX/" --recursive --only-show-errors

# --- Result -------------------------------------------------------------------
echo
echo "== Result"
echo "labelled namespaces : $(oc get namespaces -l backup -o name | wc -l)"
echo "schedules           : $(oc get schedules -n "$NS" --no-headers 2>/dev/null | wc -l)"
echo "backups             : $(oc get backups -n "$NS" --no-headers 2>/dev/null | wc -l)"
echo "S3 objects          : $(awsx s3 ls "s3://$BUCKET/$PREFIX/" --recursive | wc -l)"
echo "BSL                 : $(oc get backupstoragelocation default -n "$NS" -o jsonpath='{.status.phase}')"
