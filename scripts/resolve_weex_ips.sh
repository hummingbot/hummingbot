#!/bin/bash
# Script to resolve WEEX API and WebSocket endpoint IPs

echo "Resolving api-spot.weex.com..."
dig +short api-spot.weex.com

echo "Resolving ws-spot.weex.com..."
dig +short ws-spot.weex.com

# If dig is not available, fallback to nslookup
if ! command -v dig &> /dev/null; then
  echo "dig not found, using nslookup instead."
  echo "api-spot.weex.com:"
  nslookup api-spot.weex.com | awk '/^Address: / { print $2 }'
  echo "ws-spot.weex.com:"
  nslookup ws-spot.weex.com | awk '/^Address: / { print $2 }'
fi
