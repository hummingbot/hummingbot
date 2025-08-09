#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   scripts/build_release_image.sh [REGISTRY_IMAGE] [VERSION]
# Examples:
#   scripts/build_release_image.sh yourrepo/hummingbot v1.2.3
#   scripts/build_release_image.sh ghcr.io/yourorg/hummingbot v1.2.3

REGISTRY_IMAGE="${1:-yourrepo/hummingbot}"
VERSION="${2:-v0.0.0}"

BRANCH="$(git rev-parse --abbrev-ref HEAD || echo unknown)"
COMMIT="$(git rev-parse --short=12 HEAD || echo unknown)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "Building image: $REGISTRY_IMAGE with tags: $VERSION, $COMMIT, latest-custom"

docker build \
  --build-arg BRANCH="$BRANCH" \
  --build-arg COMMIT="$COMMIT" \
  --build-arg BUILD_DATE="$BUILD_DATE" \
  -t "$REGISTRY_IMAGE:$VERSION" \
  -t "$REGISTRY_IMAGE:$COMMIT" \
  -t "$REGISTRY_IMAGE:latest-custom" \
  .

echo "\nBuilt tags:"
echo " - $REGISTRY_IMAGE:$VERSION"
echo " - $REGISTRY_IMAGE:$COMMIT"
echo " - $REGISTRY_IMAGE:latest-custom"

echo "\nTo push:"
echo " docker push $REGISTRY_IMAGE:$VERSION"
echo " docker push $REGISTRY_IMAGE:$COMMIT"
echo " docker push $REGISTRY_IMAGE:latest-custom"
