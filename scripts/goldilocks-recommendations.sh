#!/bin/bash
# Safe local script to get resource recommendations from Goldilocks/VPA

set -euo pipefail

OUTPUT_DIR="${1:-./resource-recommendations}"
mkdir -p "$OUTPUT_DIR"

echo "🔍 Fetching resource recommendations from Goldilocks/VPA..."

# Get all VPA resources
kubectl get vpa --all-namespaces -o json | jq -r '
  .items[] | 
  select(.status.recommendation != null) |
  {
    namespace: .metadata.namespace,
    name: .metadata.name,
    containers: [
      .status.recommendation.containerRecommendations[] | {
        containerName: .containerName,
        target: .target,
        lowerBound: .lowerBound,
        upperBound: .upperBound,
        uncappedTarget: .uncappedTarget
      }
    ]
  }' > "$OUTPUT_DIR/vpa-recommendations.json"

# Generate readable report
echo "📊 Generating recommendation report..."
cat > "$OUTPUT_DIR/recommendations-report.md" << 'EOF'
# Resource Recommendations Report

Generated on: $(date)

## Summary

EOF

# Process each namespace
for ns in $(kubectl get ns -l goldilocks.fairwinds.com/enabled=true -o jsonpath='{.items[*].metadata.name}'); do
  echo "### Namespace: $ns" >> "$OUTPUT_DIR/recommendations-report.md"
  echo "" >> "$OUTPUT_DIR/recommendations-report.md"
  
  # Get VPAs for this namespace
  kubectl get vpa -n "$ns" -o json | jq -r '
    .items[] | 
    select(.status.recommendation != null) |
    "#### \(.metadata.name)\n" +
    (.status.recommendation.containerRecommendations[] | 
    "- **Container**: \(.containerName)\n" +
    "  - **Target CPU**: \(.target.cpu // "not set")\n" +
    "  - **Target Memory**: \(.target.memory // "not set")\n" +
    "  - **Range**: \(.lowerBound.cpu // "?") - \(.upperBound.cpu // "?") CPU, \(.lowerBound.memory // "?") - \(.upperBound.memory // "?") Memory\n"
    )' >> "$OUTPUT_DIR/recommendations-report.md" || echo "  No recommendations available" >> "$OUTPUT_DIR/recommendations-report.md"
  
  echo "" >> "$OUTPUT_DIR/recommendations-report.md"
done

echo "✅ Recommendations saved to $OUTPUT_DIR/"
echo "📄 View the report: $OUTPUT_DIR/recommendations-report.md"
echo "📊 Raw VPA data: $OUTPUT_DIR/vpa-recommendations.json"
echo ""
echo "🔧 Next steps:"
echo "  1. Review the recommendations in the report"
echo "  2. Manually update your HelmRelease values with appropriate resource limits"
echo "  3. Consider the target values as a baseline and adjust based on your needs"