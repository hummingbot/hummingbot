#!/bin/bash
# Test Extended API authentication to debug 401 errors

if [ -z "$1" ]; then
    echo "Usage: ./test_extended_auth.sh YOUR_API_KEY"
    echo ""
    echo "Example:"
    echo "  ./test_extended_auth.sh abc123def456..."
    exit 1
fi

API_KEY="$1"
BASE_URL="https://api.starknet.extended.exchange"

echo "============================================================"
echo "TESTING EXTENDED API AUTHENTICATION"
echo "============================================================"
echo ""
echo "Testing with API key: ${API_KEY:0:10}...${API_KEY: -10}"
echo ""

# Test 1: Public endpoint (no auth)
echo "1. Testing PUBLIC endpoint (no auth)..."
echo "   URL: $BASE_URL/api/v1/info/markets"
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$BASE_URL/api/v1/info/markets")
status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
echo "   Status: $status"

if [ "$status" = "200" ]; then
    echo "   ✅ Public endpoint works!"
else
    echo "   ❌ Public endpoint failed (unexpected)"
fi
echo ""

# Test 2: Account info endpoint (auth required)
echo "2. Testing ACCOUNT INFO endpoint (with auth)..."
echo "   URL: $BASE_URL/api/v1/user/account/info"
echo "   Headers: X-Api-Key, User-Agent"
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
    -H "X-Api-Key: $API_KEY" \
    -H "User-Agent: hummingbot-test" \
    -H "Accept: application/json" \
    "$BASE_URL/api/v1/user/account/info")
status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

echo "   Status: $status"

if [ "$status" = "200" ]; then
    echo "   ✅ Authentication works!"
    echo "   Account info: $body" | head -c 200
    echo ""
elif [ "$status" = "401" ]; then
    echo "   ❌ 401 Unauthorized - API key is invalid or not activated"
    echo "   Response: $body"
else
    echo "   Status $status: $body" | head -c 200
    echo ""
fi
echo ""

# Test 3: Balance endpoint (auth required)
echo "3. Testing BALANCE endpoint (with auth)..."
echo "   URL: $BASE_URL/api/v1/user/balance"
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
    -H "X-Api-Key: $API_KEY" \
    -H "User-Agent: hummingbot-test" \
    -H "Accept: application/json" \
    "$BASE_URL/api/v1/user/balance")
status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
body=$(echo "$response" | grep -v "HTTP_STATUS")

echo "   Status: $status"

if [ "$status" = "200" ]; then
    echo "   ✅ Balance retrieved! Auth works AND you have funds"
    echo "   Balance: $body"
elif [ "$status" = "404" ]; then
    echo "   ℹ️  404 - Auth works! This is normal if balance is zero"
    echo "   This means authentication is working, you just need to deposit USDC"
elif [ "$status" = "401" ]; then
    echo "   ❌ 401 Unauthorized - API key issue"
    echo "   Response: $body"
else
    echo "   Status $status"
    echo "   Response: $body" | head -c 200
    echo ""
fi
echo ""

# Test 4: Test with different header variations
echo "4. Testing HEADER VARIATIONS..."

# Try with Authorization header
echo "   a) Trying 'Authorization: Bearer' header..."
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
    -H "Authorization: Bearer $API_KEY" \
    -H "User-Agent: hummingbot-test" \
    "$BASE_URL/api/v1/user/account/info")
status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
echo "      Status: $status $([ "$status" = "200" ] && echo "✅" || echo "❌")"

# Try with x-api-key (lowercase)
echo "   b) Trying 'x-api-key' header (lowercase)..."
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
    -H "x-api-key: $API_KEY" \
    -H "User-Agent: hummingbot-test" \
    "$BASE_URL/api/v1/user/account/info")
status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
echo "      Status: $status $([ "$status" = "200" ] && echo "✅" || echo "❌")"

# Try with API-KEY
echo "   c) Trying 'API-KEY' header..."
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
    -H "API-KEY: $API_KEY" \
    -H "User-Agent: hummingbot-test" \
    "$BASE_URL/api/v1/user/account/info")
status=$(echo "$response" | grep "HTTP_STATUS" | cut -d: -f2)
echo "      Status: $status $([ "$status" = "200" ] && echo "✅" || echo "❌")"

echo ""
echo "============================================================"
echo "DIAGNOSIS:"
echo "============================================================"
echo ""
echo "Based on the results above:"
echo ""
echo "If ALL tests show 401:"
echo "  → Your API key is invalid, expired, or not activated"
echo "  → Solution: Go to https://app.extended.exchange/api-management"
echo "  → Regenerate your API key"
echo ""
echo "If account info is 200 but balance is 404:"
echo "  → ✅ Auth is working perfectly!"
echo "  → You just need to deposit USDC to your Extended account"
echo ""
echo "If one header variation worked (showed 200):"
echo "  → We need to update the connector to use that header name"
echo ""
echo "============================================================"

