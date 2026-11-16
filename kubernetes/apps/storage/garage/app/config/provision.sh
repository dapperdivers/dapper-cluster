#!/bin/sh
# Idempotently create Garage buckets and import their access keys via the v2
# admin API. Keys are generated in Infisical (/Infrastructure/Garage) so the
# consuming apps can read the same values through their own ExternalSecrets.
#
# BUCKETS: space-separated "<bucket>:<KEY_PREFIX>" pairs. For each, the env
# must hold GARAGE_<KEY_PREFIX>_ACCESS_KEY_ID / _SECRET_ACCESS_KEY.
set -eu

API="${GARAGE_ADMIN_URL:?}"
AUTH="Authorization: Bearer ${GARAGE_ADMIN_TOKEN:?}"

# GET/POST helper: prints the body, returns non-zero on HTTP >= 400.
api() {
  endpoint="$1"; shift
  if [ $# -gt 0 ]; then
    curl -fsS -H "$AUTH" -H 'Content-Type: application/json' -X POST -d "$1" "$API/v2/$endpoint"
  else
    curl -fsS -H "$AUTH" "$API/v2/$endpoint"
  fi
}

first_id() { grep -o '"id":"[0-9a-f]*"' | head -n1 | cut -d'"' -f4; }

echo "waiting for Garage admin API at $API"
until curl -fsS "$API/health" >/dev/null 2>&1; do sleep 5; done

for spec in ${BUCKETS:?}; do
  bucket="${spec%%:*}"
  prefix="${spec#*:}"
  eval "key_id=\${GARAGE_${prefix}_ACCESS_KEY_ID:?}"
  eval "key_secret=\${GARAGE_${prefix}_SECRET_ACCESS_KEY:?}"

  if bucket_id=$(api "GetBucketInfo?globalAlias=${bucket}" 2>/dev/null | first_id) && [ -n "$bucket_id" ]; then
    echo "bucket ${bucket}: exists (${bucket_id})"
  else
    bucket_id=$(api CreateBucket "{\"globalAlias\":\"${bucket}\"}" | first_id)
    echo "bucket ${bucket}: created (${bucket_id})"
  fi

  if api "GetKeyInfo?id=${key_id}" >/dev/null 2>&1; then
    echo "key ${key_id}: exists"
  else
    api ImportKey "{\"accessKeyId\":\"${key_id}\",\"secretAccessKey\":\"${key_secret}\",\"name\":\"${bucket}\"}" >/dev/null
    echo "key ${key_id}: imported"
  fi

  api AllowBucketKey "{\"bucketId\":\"${bucket_id}\",\"accessKeyId\":\"${key_id}\",\"permissions\":{\"read\":true,\"write\":true,\"owner\":true}}" >/dev/null
  echo "key ${key_id}: read/write/owner on ${bucket}"
done
echo "done"
