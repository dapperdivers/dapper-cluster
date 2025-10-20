#!/bin/bash
# Script to identify HelmReleases that need resource limit updates based on VPA
# Usage: ./update-helmreleases-from-vpa.sh

set -e

REPO_ROOT="${1:-/home/derek/projects/dapper-cluster}"
APPS_DIR="$REPO_ROOT/kubernetes/apps"

echo "=========================================="
echo "HelmRelease Resource Limit Update Helper"
echo "=========================================="
echo ""
echo "Using repository: $REPO_ROOT"
echo ""

# Function to convert CPU from string to millicore number
cpu_to_millis() {
    local cpu=$1
    if [[ $cpu == *m ]]; then
        echo "${cpu%m}"
    else
        # Assume it's cores, convert to millicores
        echo "$((${cpu%.*} * 1000))"
    fi
}

# Function to convert memory bytes to Mi
mem_to_mi() {
    local bytes=$1
    echo "$((bytes / 1048576))"
}

echo "Fetching VPA recommendations..."
kubectl get vpa -A -o json > /tmp/vpa-all.json

echo ""
echo "=========================================="
echo "Observability Namespace - Priority Updates"
echo "=========================================="
echo ""

# Focus on observability namespace workloads
jq -r '.items[] | select(.metadata.namespace == "observability") | select(.status.recommendation.containerRecommendations) | {
    workload: .spec.targetRef.name,
    container: .status.recommendation.containerRecommendations[0].containerName,
    cpu_target: .status.recommendation.containerRecommendations[0].target.cpu,
    cpu_upper: .status.recommendation.containerRecommendations[0].upperBound.cpu,
    mem_target: .status.recommendation.containerRecommendations[0].target.memory,
    mem_upper: .status.recommendation.containerRecommendations[0].upperBound.memory
} | @json' /tmp/vpa-all.json | while read -r line; do
    workload=$(echo "$line" | jq -r '.workload')
    container=$(echo "$line" | jq -r '.container')
    cpu_target=$(echo "$line" | jq -r '.cpu_target')
    cpu_upper=$(echo "$line" | jq -r '.cpu_upper')
    mem_target=$(echo "$line" | jq -r '.mem_target')
    mem_upper=$(echo "$line" | jq -r '.mem_upper')

    # Convert to Mi
    mem_target_mi=$(mem_to_mi "$mem_target")
    mem_upper_mi=$(mem_to_mi "$mem_upper")

    echo "Workload: $workload (container: $container)"
    echo "  VPA Recommendations:"
    echo "    resources:"
    echo "      requests:"
    echo "        cpu: $cpu_target"
    echo "        memory: ${mem_target_mi}Mi"
    echo "      limits:"
    echo "        cpu: $cpu_upper"
    echo "        memory: ${mem_upper_mi}Mi"

    # Find the helmrelease file
    helmrelease_file=$(find "$APPS_DIR/observability" -name "helmrelease.yaml" -type f 2>/dev/null | xargs grep -l "name: $workload" 2>/dev/null | head -1)

    if [ -n "$helmrelease_file" ]; then
        echo "  File: $helmrelease_file"
    fi
    echo ""
done

echo "=========================================="
echo "Network Namespace - High CPU Workloads"
echo "=========================================="
echo ""

# Network namespace
jq -r '.items[] | select(.metadata.namespace == "network") | select(.status.recommendation.containerRecommendations) | {
    workload: .spec.targetRef.name,
    container: .status.recommendation.containerRecommendations[0].containerName,
    cpu_target: .status.recommendation.containerRecommendations[0].target.cpu,
    cpu_upper: .status.recommendation.containerRecommendations[0].upperBound.cpu,
    mem_target: .status.recommendation.containerRecommendations[0].target.memory,
    mem_upper: .status.recommendation.containerRecommendations[0].upperBound.memory
} | @json' /tmp/vpa-all.json | while read -r line; do
    workload=$(echo "$line" | jq -r '.workload')
    container=$(echo "$line" | jq -r '.container')
    cpu_target=$(echo "$line" | jq -r '.cpu_target')
    cpu_upper=$(echo "$line" | jq -r '.cpu_upper')
    mem_target=$(echo "$line" | jq -r '.mem_target')
    mem_upper=$(echo "$line" | jq -r '.mem_upper')

    mem_target_mi=$(mem_to_mi "$mem_target")
    mem_upper_mi=$(mem_to_mi "$mem_upper")

    echo "Workload: $workload (container: $container)"
    echo "  VPA Recommendations:"
    echo "    resources:"
    echo "      requests:"
    echo "        cpu: $cpu_target"
    echo "        memory: ${mem_target_mi}Mi"
    echo "      limits:"
    echo "        cpu: $cpu_upper"
    echo "        memory: ${mem_upper_mi}Mi"
    echo ""
done

echo "=========================================="
echo "Media Namespace - High CPU Workloads"
echo "=========================================="
echo ""

# Media namespace - only show high CPU workloads
jq -r '.items[] | select(.metadata.namespace == "media") | select(.status.recommendation.containerRecommendations) | select(.status.recommendation.containerRecommendations[0].upperBound.cpu | test("^[0-9]+m$") | not or (.status.recommendation.containerRecommendations[0].upperBound.cpu | rtrimstr("m") | tonumber) > 100) | {
    workload: .spec.targetRef.name,
    cpu_target: .status.recommendation.containerRecommendations[0].target.cpu,
    cpu_upper: .status.recommendation.containerRecommendations[0].upperBound.cpu,
    mem_target: .status.recommendation.containerRecommendations[0].target.memory,
    mem_upper: .status.recommendation.containerRecommendations[0].upperBound.memory
} | @json' /tmp/vpa-all.json 2>/dev/null | while read -r line; do
    workload=$(echo "$line" | jq -r '.workload')
    cpu_target=$(echo "$line" | jq -r '.cpu_target')
    cpu_upper=$(echo "$line" | jq -r '.cpu_upper')
    mem_target=$(echo "$line" | jq -r '.mem_target')
    mem_upper=$(echo "$line" | jq -r '.mem_upper')

    mem_target_mi=$(mem_to_mi "$mem_target")
    mem_upper_mi=$(mem_to_mi "$mem_upper")

    echo "Workload: media/$workload"
    echo "  CPU: $cpu_target (request) / $cpu_upper (limit)"
    echo "  Memory: ${mem_target_mi}Mi (request) / ${mem_upper_mi}Mi (limit)"
    echo ""
done

rm -f /tmp/vpa-all.json

echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Visit Goldilocks Dashboard: https://goldilocks.chelonianlabs.com"
echo "2. For each workload above, update its HelmRelease:"
echo "   - Edit kubernetes/apps/<namespace>/<workload>/app/helmrelease.yaml"
echo "   - Add/update the resources section under 'values:'"
echo "   - Use VPA recommendations as a starting point"
echo "   - For critical workloads, add 50-100% headroom to limits"
echo ""
echo "3. Example HelmRelease resource block:"
echo "   values:"
echo "     resources:"
echo "       requests:"
echo "         cpu: <target_cpu>"
echo "         memory: <target_memory>"
echo "       limits:"
echo "         cpu: <upper_cpu> or 2x target for burst workloads"
echo "         memory: <upper_memory>"
echo ""
echo "4. Commit and push changes - Flux will reconcile automatically"
echo ""
