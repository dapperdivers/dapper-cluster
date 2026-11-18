#!/usr/bin/env bash
# Send one message to a kagent agent from inside the cluster (no port-forward, no SSO)
# and print its final answer. The full A2A response is saved for inspection.
#
#   ask-agent.sh <agent> '<prompt>' [outfile]
#
# Needs kubectl access to the kagent namespace, and jq. The call blocks until the agent
# finishes (up to TIMEOUT seconds, default 600). Each call starts a new session.
set -euo pipefail

agent="${1:?usage: ask-agent.sh <agent> '<prompt>' [outfile]}"
prompt="${2:?usage: ask-agent.sh <agent> '<prompt>' [outfile]}"
out="${3:-$(mktemp -t "kagent-${agent}-XXXXXX.json")}"
timeout="${TIMEOUT:-600}"

body=$(jq -nc --arg t "$prompt" --arg id "ask-$(date +%s%N)" \
  '{jsonrpc:"2.0",id:1,method:"SendMessage",params:{message:{role:"ROLE_USER",messageId:$id,parts:[{text:$t}]}}}')

kubectl exec -n kagent deploy/kagent-controller -- wget -qO- --timeout="$timeout" \
  --header='Content-Type: application/json' --header='A2A-Version: 1.0' \
  --post-data="$body" "http://localhost:8083/agents/kagent/${agent}" >"$out"

state=$(jq -r '.result.task.status.state // empty' "$out")
if [ -z "$state" ]; then
  echo "no task in the response (agent missing or not Ready?):" >&2
  head -c 600 "$out" >&2
  echo >&2
  exit 1
fi

echo "state: $state" >&2
# Token usage is reported by kagent-default agents only.
jq -r '.result.task.metadata["https://kagent.dev/extensions/usage/v1"] // empty
       | "tokens: in=\(.inputTokens) out=\(.outputTokens)"' "$out" >&2
# Tool calls made, by name (data parts marked function_call).
jq -r '[.result.task.artifacts[]?.parts[]?
        | select(.metadata["kagent.dev/a2a/part-type"]? == "function_call")
        | .data.name // .data.data.name // "?"] | group_by(.) | map("\(.[0]) x\(length)")
       | if length > 0 then "tool calls: " + join(", ") else "tool calls: none" end' "$out" >&2
echo "saved: $out" >&2

# The answer is the last artifact that has text; earlier ones are narration. The Claude
# harness splits it into many small parts, so join them.
jq -r '[.result.task.artifacts[]? | select(any(.parts[]?; .text))] | last
       | [.parts[]? | select(.metadata["kagent.dev/a2a/thought"]? != true) | .text // empty] | join("")' "$out"
