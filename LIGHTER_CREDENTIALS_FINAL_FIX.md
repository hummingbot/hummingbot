# Lighter Connector Credentials - Final Fix

## Problem

The connector was asking for credentials that didn't match what Lighter actually provides:
- ❌ **Was asking**: Private Key, Account Index, API Key Index
- ✅ **Should ask**: Public Key, Private Key, API Key Index

## What Lighter Actually Gives You

When you generate an API key on Lighter, you receive **exactly 3 things**:
1. **Public Key**
2. **Private Key**  
3. **API Key Index** (e.g., 2, 3, 4)

There is NO "Account Index" in the API key generation - that was a misunderstanding.

## Changes Made

### 1. Updated Config Map (`lighter_perpetual_utils.py`)

**Before:**
```python
lighter_perpetual_api_key_private_key: SecretStr  # Confusing name
lighter_perpetual_account_index: int              # Doesn't exist!
lighter_perpetual_api_key_index: int
```

**After:**
```python
lighter_perpetual_public_key: SecretStr           # Clear
lighter_perpetual_private_key: SecretStr          # Clear
lighter_perpetual_api_key_index: int              # Clear
```

### 2. Updated Auth Class (`lighter_perpetual_auth.py`)

**Before:**
```python
def __init__(self, api_key_private_key: str, account_index: int, api_key_index: int):
    self.api_key_private_key = api_key_private_key
    self.account_index = account_index
    self.api_key_index = api_key_index
```

**After:**
```python
def __init__(self, public_key: str, private_key: str, api_key_index: int):
    self.public_key = public_key
    self.private_key = private_key
    self.api_key_index = api_key_index
```

**Headers sent:**
```python
headers["Authorization"] = f"Bearer {self.private_key}"
headers["X-Lighter-Public-Key"] = self.public_key
headers["X-Api-Key-Index"] = str(self.api_key_index)
```

### 3. Updated Main Connector (`lighter_perpetual_derivative.py`)

**Before:**
```python
def __init__(
    self,
    lighter_perpetual_api_key_private_key: str,
    lighter_perpetual_account_index: int,
    lighter_perpetual_api_key_index: int,
    ...
)
```

**After:**
```python
def __init__(
    self,
    lighter_perpetual_public_key: str,
    lighter_perpetual_private_key: str,
    lighter_perpetual_api_key_index: int,
    ...
)
```

### 4. Updated Documentation

**Updated connection flow:**
```bash
>>> connect lighter_perpetual

# Prompt 1
Enter your Lighter Public Key >>> 
[Paste Public Key]

# Prompt 2
Enter your Lighter Private Key >>> 
[Paste Private Key]

# Prompt 3
Enter your Lighter API Key Index >>> 
[Enter number, e.g., 3]
```

## New Connection Prompts

The connector will now ask:

1. ✅ **Enter your Lighter Public Key**
   - Paste the Public Key from Lighter

2. ✅ **Enter your Lighter Private Key**
   - Paste the Private Key from Lighter

3. ✅ **Enter your Lighter API Key Index**
   - Enter the number from Lighter (e.g., 3)

## No More Confusion!

- ✅ All 3 credentials come directly from Lighter API key generation
- ✅ No need to search for "Account Index" anywhere
- ✅ Clear, simple prompts that match what Lighter gives you
- ✅ Proper header names for authentication

## How to Use Updated Connector

### 1. Rebuild Docker Image

```bash
docker stop hb-lighter 2>/dev/null; docker rm hb-lighter 2>/dev/null
docker build -t hummingbot-custom .
```

### 2. Run Container

```bash
docker run -it --rm --name hb-lighter \
  -v $(pwd)/conf:/home/hummingbot/conf \
  -v $(pwd)/data:/home/hummingbot/data \
  -v $(pwd)/logs:/home/hummingbot/logs \
  hummingbot-custom
```

### 3. Connect with Correct Credentials

```bash
>>> connect lighter_perpetual

Enter your Lighter Public Key >>> 
[Paste your Public Key from Lighter]

Enter your Lighter Private Key >>> 
[Paste your Private Key from Lighter]

Enter your Lighter API Key Index >>> 
3  # Or whatever number Lighter gave you
```

## Files Modified

1. ✅ `lighter_perpetual_utils.py` - Updated config map
2. ✅ `lighter_perpetual_auth.py` - Updated auth parameters and headers
3. ✅ `lighter_perpetual_derivative.py` - Updated constructor parameters
4. ✅ `USE_LIGHTER_PERPETUAL_CONNECTOR.md` - Updated documentation

## Summary

The connector now correctly asks for the **exact 3 credentials** that Lighter provides:
1. Public Key
2. Private Key
3. API Key Index

No more confusion about "Account Index" or which key goes where!

---

**Update Date**: October 11, 2025  
**Status**: ✅ Fixed and Ready for Testing  
**Next Step**: Rebuild Docker and test connection

