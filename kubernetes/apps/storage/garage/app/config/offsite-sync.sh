#!/bin/sh
# Mirror Garage buckets to Cloudflare R2 so backups survive losing Ceph (which
# holds both the databases and Garage). `sync` mirrors deletions too, so R2
# follows the source's own retention (e.g. barman's 30d) instead of growing.
#
# Guard: if a source bucket has fewer than half the objects of its R2 copy,
# something is wrong with the source (wiped, bad credentials returning an
# empty listing, ...): refuse to sync rather than propagate the loss.
#
# SYNC_BUCKETS: space-separated Garage bucket names. Each goes to
# r2:<R2_BUCKET>/garage-offsite/<bucket>/.
set -eu

: "${R2_BUCKET:?}" "${SYNC_BUCKETS:?}"

count() { rclone size --json "$1" 2>/dev/null | sed -n 's/.*"count":\([0-9]*\).*/\1/p'; }

status=0
for bucket in $SYNC_BUCKETS; do
  src="garage:${bucket}"
  dst="r2:${R2_BUCKET}/garage-offsite/${bucket}"

  src_n=$(count "$src")
  if [ -z "$src_n" ]; then
    echo "ERROR ${bucket}: cannot list source ${src}"
    status=1; continue
  fi
  dst_n=$(count "$dst"); dst_n=${dst_n:-0}
  echo "${bucket}: source=${src_n} objects, offsite=${dst_n} objects"

  if [ "$dst_n" -gt 0 ] && [ $((src_n * 2)) -lt "$dst_n" ]; then
    echo "ERROR ${bucket}: source has under half the offsite objects; refusing to sync"
    status=1; continue
  fi

  rclone sync "$src" "$dst" --fast-list --stats-one-line --stats=0 -v
  echo "${bucket}: synced"
done
exit $status
