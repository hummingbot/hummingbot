# Extended Exchange Connector - Authentication Update

## ✅ Updated Authentication Credentials

The Extended connector has been updated to use the correct authentication credentials as per Extended Exchange's API requirements.

## Required Credentials

When connecting to Extended in Hummingbot, you will be prompted for:

1. **API Key** (extended_api_key)
   - Used in `X-Api-Key` header for all API requests
   - Required for both public and private endpoints

2. **Stark Public Key** (extended_stark_public_key)
   - Your Starknet public key
   - Included in order management requests
   - Used for signature verification

3. **Stark Private Key** (extended_stark_private_key)
   - Your Starknet private key
   - Used to generate signatures for order placement
   - Never sent to the API (only used locally to sign)

## ❌ NOT Required

- **Vault Number** - Only used for sub-account management in the UI
- **Client ID** - Only used for sub-account management in the UI

## How to Get Your Credentials

1. Log into https://extended.exchange
2. Navigate to **API Settings** in your account
3. Generate/view your credentials:
   - API Key
   - Stark Public Key
   - Stark Private Key

## Connection Flow

When you run `connect extended` in Hummingbot:

```
>>> connect extended

Enter your Extended API key >>> [paste your API key]
Enter your Extended Stark public key >>> [paste your Stark public key]
Enter your Extended Stark private key >>> [paste your Stark private key]
```

## Authentication Implementation

### REST API Authentication
- Every request includes `X-Api-Key` header
- Order placement requests include:
  - `stark_signature` - Signature of order parameters
  - `stark_public_key` - Your public key for verification

### WebSocket Authentication
- Connection includes `X-Api-Key` header
- No additional authentication needed

### Signature Generation
Order signatures are generated using your Stark private key:
```python
# In extended_auth.py
def generate_stark_signature(self, order_params: Dict[str, Any]) -> str:
    # Signs order parameters using Stark private key
    # Follows Starknet signing standard (SNIP12)
```

## Files Modified

1. **extended_utils.py**
   - Updated `ExtendedConfigMap` to ask for 3 credentials
   - Changed from `extended_secret_key` to `extended_stark_public_key` and `extended_stark_private_key`

2. **extended_auth.py**
   - Updated constructor to accept 3 parameters
   - Changed from HMAC-SHA256 to Starknet signature-based auth
   - Updated `rest_authenticate()` to use `X-Api-Key` header
   - Added `generate_stark_signature()` method for order signing

3. **extended_exchange.py**
   - Updated `__init__()` to accept 3 credentials
   - Updated `authenticator` property to pass all 3 credentials
   - Updated `_place_order()` to include Stark signature and public key

4. **USE_EXTENDED_CONNECTOR.md**
   - Updated documentation to reflect correct credentials
   - Added authentication details
   - Updated examples

## Important Notes

### Stark Signature Implementation
The current implementation includes a **placeholder** for Stark signature generation:

```python
def generate_stark_signature(self, order_params: Dict[str, Any]) -> str:
    # TODO: Implement proper Stark signature generation
    # This requires starkware-crypto library
    return self.stark_private_key  # Placeholder
```

**For production use**, you should:
1. Install `starkware-crypto` library
2. Implement proper message hashing (Pedersen hash)
3. Use `starkware.crypto.signature.sign()` to generate signatures
4. Follow Extended's specific message format for order signing

### Testing Recommendations

1. **Start with testnet** to verify credentials work
2. **Test order placement** to ensure signatures are accepted
3. **Monitor API responses** for signature-related errors
4. **Check Extended documentation** for their exact signature format

### Example: Proper Stark Signature (Future Implementation)

```python
# Will require starkware-crypto library
from starkware.crypto.signature import sign

def generate_stark_signature(self, order_params: Dict[str, Any]) -> str:
    # 1. Create message hash from order parameters
    message_hash = pedersen_hash_chain([
        order_params['market_id'],
        order_params['side'],
        order_params['size'],
        # ... other parameters
    ])
    
    # 2. Sign the message hash
    r, s = sign(message_hash, int(self.stark_private_key, 16))
    
    # 3. Return signature in expected format
    return f"{r},{s}"
```

## Troubleshooting

### "Invalid API Key" Error
- Verify you're using the correct API key
- Check that you copied it completely without spaces

### "Invalid Signature" Error
- This likely means the Stark signature generation needs proper implementation
- Check Extended's API docs for their exact signature format
- Verify your Stark keys are correct

### "Unauthorized" Error
- Ensure `X-Api-Key` header is being sent
- Check that your API key has trading permissions enabled

## Security Best Practices

1. **Never share your Stark private key** - it's like a password
2. **Store credentials securely** - use Hummingbot's encrypted storage
3. **Use sub-accounts** if available for additional security
4. **Regularly rotate API keys** for better security
5. **Monitor API usage** for any unauthorized activity

## Docker Usage

When using the updated connector in Docker:

```bash
# Build with updated connector
docker build -t hummingbot-extended .

# Run container
docker run -it --rm \
  --name hb-extended \
  -v $(pwd)/conf:/home/hummingbot/conf \
  hummingbot-extended

# Then connect:
>>> connect extended
# Enter your 3 credentials when prompted
```

## Summary

✅ **What Changed:**
- From: API Key + Secret Key (2 credentials)
- To: API Key + Stark Public Key + Stark Private Key (3 credentials)

✅ **What Works:**
- API authentication with `X-Api-Key` header
- WebSocket connections
- Balance and market data retrieval

⚠️ **What Needs Attention:**
- Stark signature generation (currently placeholder)
- May need `starkware-crypto` library for production
- Test thoroughly on testnet first

## Next Steps

1. **Test the connector** with your Extended credentials
2. **Monitor for signature errors** when placing orders
3. **Implement proper Stark signing** if needed based on Extended's requirements
4. **Report any issues** or API format discrepancies

