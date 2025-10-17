# Lighter Connector Credential Prompts Update

## Changes Made

Updated the Lighter perpetual connector to have clearer, more accurate credential prompts that match what Lighter actually provides.

## Files Modified

### 1. `hummingbot/connector/derivative/lighter_perpetual/lighter_perpetual_utils.py`

**Changed credential prompts to be more descriptive:**

#### Before:
```python
"prompt": "Enter your Lighter API key private key"
"prompt": "Enter your Lighter account index"
"prompt": "Enter your Lighter API key index (2-254, default: 2)"
```

#### After:
```python
"prompt": "Enter your Lighter Private Key (from API key generation)"
"prompt": "Enter your Lighter Account Index (check your account settings, e.g., 3)"
"prompt": "Enter your Lighter API Key Index (from API key generation, e.g., 2, 3, 4)"
```

**Also removed default value for API Key Index:**
- Changed from `default=2` to `default=...` (required field)
- This prevents users from accidentally using wrong index

### 2. `USE_LIGHTER_PERPETUAL_CONNECTOR.md`

**Added clear credential mapping section:**

Shows exactly what Lighter provides and how it maps to connector prompts:

```
Lighter Provides:                    →  Connector Asks:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Private Key                          →  "Enter your Lighter Private Key"
Account Index (from account page)    →  "Enter your Lighter Account Index"
API Key Index (from key generation)  →  "Enter your Lighter API Key Index"
Public Key                           →  (Not currently asked - optional)
```

**Updated Connection Flow with detailed examples:**

- Shows step-by-step what each prompt means
- Includes example values
- Clarifies NOT to enter Public Key when asked for Private Key

## What Lighter Actually Provides

When you generate an API key on Lighter, you get:

1. ✅ **API Key Index** (e.g., 2, 3, 4)
2. ✅ **Public Key** (0x1234...)
3. ✅ **Private Key** (abc123...)

And separately, you have:

4. ✅ **Account Index** (your account number on Lighter, e.g., 0, 3, 5)

## How to Use

### When Connecting to Lighter

```bash
>>> connect lighter_perpetual

# Prompt 1: Paste your Private Key (NOT Public Key)
Enter your Lighter Private Key (from API key generation) >>> 
abc123def456...

# Prompt 2: Enter YOUR account number
Enter your Lighter Account Index (check your account settings, e.g., 3) >>> 
3

# Prompt 3: Enter the API Key Index from generation
Enter your Lighter API Key Index (from API key generation, e.g., 2, 3, 4) >>> 
3
```

## Finding Your Account Index

Your **Account Index** is your account number on Lighter. To find it:

### Option 1: Lighter Dashboard
- Log into Lighter
- Go to Account Settings or Profile
- Look for "Account ID" or "Account Index"

### Option 2: API Call (if you have credentials)
```bash
curl https://mainnet.zklighter.elliot.ai/api/v1/account \
  -H "Authorization: Bearer YOUR_PRIVATE_KEY" \
  -H "X-Api-Key-Index: YOUR_API_KEY_INDEX"
```

The response should include your account index.

### Option 3: Ask Lighter Support
If unsure, contact Lighter support to confirm your account index.

## Common Mistakes to Avoid

❌ **DON'T** enter Public Key when asked for Private Key
❌ **DON'T** use API Key Index as Account Index (they're different!)
❌ **DON'T** assume Account Index is 0 (it could be 3, 5, or any number)

✅ **DO** enter Private Key from API key generation
✅ **DO** check your actual Account Index in Lighter settings
✅ **DO** use the API Key Index from API key generation

## Testing Connection

After connecting, verify it works:

```bash
>>> balance lighter_perpetual
# Should show your USDC balance

>>> status
# Should show lighter_perpetual connected
```

## Rebuilding Docker

If using Docker, rebuild the image with updated prompts:

```bash
# Rebuild
docker build -t hummingbot-custom .

# Run
docker run -it --rm --name hb-lighter \
  -v $(pwd)/conf:/home/hummingbot/conf \
  -v $(pwd)/data:/home/hummingbot/data \
  -v $(pwd)/logs:/home/hummingbot/logs \
  hummingbot-custom

# Connect
>>> connect lighter_perpetual
```

## Summary

The connector now has **clearer prompts** that:
1. Distinguish between Private Key and Public Key
2. Clarify that Account Index is YOUR account number (not from API key)
3. Show that API Key Index comes from API key generation
4. Provide examples (e.g., 3) to guide users
5. No longer assume Account Index defaults to 0

This should eliminate confusion about which credentials to enter where!

---

**Update Date**: October 11, 2025  
**Status**: ✅ Complete - Ready for Docker Rebuild

