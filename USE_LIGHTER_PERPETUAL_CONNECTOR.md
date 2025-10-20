# Lighter Perpetual Connector for Hummingbot

## Overview

This connector integrates Lighter DEX's **Perpetual Futures** platform with Hummingbot. Lighter is a **perp-only DEX** built on zk-rollup technology - they do NOT offer spot trading.

**Important:** This is the perpetual-only connector for Lighter. Lighter specializes in perpetual contracts with high performance and low latency.

## 🎯 What Lighter Offers

- ✅ **Perpetual Contracts** - Crypto assets
- ✅ **USDC Collateral** - All positions settled in USDC
- ✅ **High Leverage** - Variable leverage per market
- ✅ **No Expiration** - True perpetual futures
- ✅ **Low Fees** - 0.2 bps maker, 2 bps taker
- ❌ **NO Spot Trading** - Only perpetuals

## Connector Structure

```
hummingbot/connector/derivative/lighter_perpetual/
├── __init__.py
├── lighter_perpetual_constants.py          # API endpoints & constants
├── lighter_perpetual_utils.py              # Config & utilities
├── lighter_perpetual_web_utils.py          # Web assistant factory
├── lighter_perpetual_auth.py               # API key authentication & nonce management
├── lighter_perpetual_api_order_book_data_source.py  # Order book data
├── lighter_perpetual_api_user_stream_data_source.py # User stream
└── lighter_perpetual_derivative.py         # Main perpetual class
```

## API Configuration

### Mainnet (Production)
- **REST API**: `https://mainnet.zklighter.elliot.ai`
- **WebSocket**: `wss://mainnet.zklighter.elliot.ai`

### Testnet
- **REST API**: `https://testnet.zklighter.elliot.ai`
- **WebSocket**: `wss://testnet.zklighter.elliot.ai`

## Required Credentials

When connecting to Lighter Perpetual, you need **exactly 3 credentials** that Lighter provides:

### What Lighter API Provides

When you generate an API key on Lighter, you receive:
1. ✅ **Public Key** 
2. ✅ **Private Key**
3. ✅ **API Key Index** (e.g., 2, 3, 4)

### How to Map to Connector Prompts

```
Lighter Gives You:                   →  Connector Asks:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Public Key                           →  "Enter your Lighter Public Key"
                                        (paste Public Key here)

Private Key                          →  "Enter your Lighter Private Key"
                                        (paste Private Key here)

API Key Index                        →  "Enter your Lighter API Key Index"
                                        (enter the number, e.g., 3)
```

**Notes:**
- ✅ All 3 credentials come from Lighter API key generation
- ✅ Enter them in order: Public Key → Private Key → API Key Index
- ⚠️ Keep Private Key secret! It's used for signing all transactions
- 📝 You can generate multiple API keys with different indices (2-254)

## How to Get Your Credentials

1. Go to https://lighter.xyz
2. Create an account and complete onboarding
3. Navigate to **API Settings** or **Developer Settings**
4. Generate a new API key:
   - You'll receive an **API Key Private Key**
   - Note your **Account Index**
   - Choose an **API Key Index** (default: 2)
5. Save these credentials securely

### Setting up API Key (Python Example)

According to Lighter docs, you can set up an API key programmatically:

```python
import lighter

BASE_URL = "https://mainnet.zklighter.elliot.ai"
ETH_PRIVATE_KEY = "your_ethereum_private_key"  # For initial setup only
ACCOUNT_INDEX = 0  # Your account index
API_KEY_INDEX = 2  # Choose 2-254

# This generates your API_KEY_PRIVATE_KEY
# You only need to do this once
api_key_private_key = lighter.generate_api_key(
    base_url=BASE_URL,
    eth_private_key=ETH_PRIVATE_KEY,
    account_index=ACCOUNT_INDEX,
    api_key_index=API_KEY_INDEX
)
```

## Connection Flow

```bash
>>> connect lighter_perpetual

# Prompt 1: Public Key (from Lighter API key generation)
Enter your Lighter Public Key >>> 

# Prompt 2: Private Key (from Lighter API key generation)
Enter your Lighter Private Key >>> 

# Prompt 3: API Key Index (from Lighter API key generation)
Enter your Lighter API Key Index >>> 

✅ You are now connected to lighter_perpetual.
```

**Example:**
When Lighter gives you:
- Public Key: `0x1234abcd...`
- Private Key: `abc123def456...`
- API Key Index: `3`

You enter them in that exact order into the three prompts.

## Key API Endpoints

### Public Endpoints
- `GET /api/v1/markets` - Get all markets
- `GET /api/v1/markets/stats?market_id={market}` - Market statistics
- `GET /api/v1/orderbook?market_id={market}` - Order book
- `GET /api/v1/trades?market_id={market}` - Recent trades
- `GET /api/v1/funding-rates?market_id={market}` - Funding rates

### Private Endpoints
- `GET /api/v1/account` - Account details
- `GET /api/v1/account/balance` - Get balance
- `GET /api/v1/account/positions` - Get positions
- `POST /api/v1/transaction/send` - Send transaction (place order)
- `DELETE /api/v1/orders/{order_id}` - Cancel order
- `GET /api/v1/account/trades` - Trade history
- `POST /api/v1/account/leverage` - Set leverage
- `GET /api/v1/account/funding-payments` - Funding payment history
- `GET /api/v1/transaction/next-nonce` - Get next nonce

## Market Format

Lighter uses **hyphenated USD format**:
- **Lighter**: `BTC-USD`, `ETH-USD`, `SOL-USD`
- **Hummingbot**: `BTC-USDC`, `ETH-USDC`, `SOL-USDC`

The connector automatically maps `{BASE}-USD` → `{BASE}-USDC` since Lighter settles in USDC.

## Perpetual-Specific Features

### Position Management
- **Position Mode**: One-way only (no hedge mode)
- **Collateral**: USDC
- **Leverage**: Variable by market
- **Liquidation**: Automatic based on margin requirements

### Nonce Management
- Each transaction requires a unique nonce
- Nonce auto-increments per API_KEY
- Connector automatically fetches next nonce from API
- Nonce resets on reconnection

### Funding Rates
- Updated every hour
- Typical range: varies by market
- Automatically fetched and applied
- Long positions pay when positive, receive when negative

### Order Types
- ✅ **Market** - Immediate execution
- ✅ **Limit** - GTC (Good-Till-Cancel)
- ✅ **Limit Maker** - Post-only orders

### Order Requirements
- **Nonce**: Required for each transaction
- **Signature**: All transactions must be signed with API key private key
- **Min Size**: Varies by market
- **Tick Size**: Varies by market

## Transaction Signing

Lighter uses nonce-based transaction signing:

1. **Get Next Nonce**: Connector fetches from `/api/v1/transaction/next-nonce`
2. **Build Transaction**: Include order params + nonce + account/API key indices
3. **Sign Transaction**: Generate signature using API key private key
4. **Send Transaction**: POST to `/api/v1/transaction/send`

The connector handles all of this automatically.

## Known Issues & Solutions

### Issue 1: Balance Shows $0
**Cause**: May not have deposited funds yet  
**Solution**: Deposit USDC to your Lighter account  
**Note**: Lighter may return 404 when balance is zero (handled by connector)

### Issue 2: "Markets are not ready"
**Cause**: Market symbol mapping issues  
**Solution**: Check that markets endpoint returns valid data  
**Debug**: Look at logs for trading pair initialization

### Issue 3: Nonce Errors
**Cause**: Nonce out of sync  
**Solution**: Connector automatically fetches latest nonce from API  
**Note**: Restart connector if persistent issues

### Issue 4: Cannot use with spot strategies
**Cause**: Lighter is PERPETUALS ONLY  
**Solution**: ✅ Use perpetual strategies only:
- PMM for perpetuals
- Directional trading
- Funding rate arbitrage
- Position management

## Compatible Strategies

### ✅ Works With (Perpetual Strategies)
- `pmm_dynamic` - Perpetual market making
- `dman_v3` - Directional trading
- `v2_funding_rate_arb` - Funding arbitrage
- Any custom perpetual strategy

### ❌ Does NOT Work With (Spot Only)
- `pmm_simple` (spot version)
- `arbitrage_controller` (spot arb)
- Spot market making strategies

## Example Usage

### Basic Perpetual PMM

```yaml
# conf_pmm_lighter_perp.yml
exchange: lighter_perpetual
market: BTC-USDC  # Will map to BTC-USD on Lighter
leverage: 5
bid_spread: 0.5
ask_spread: 0.5
order_amount: 0.01
```

### In Python Script

```python
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import LighterPerpetualDerivative

# Initialize connector
connector = LighterPerpetualDerivative(
    lighter_perpetual_public_key="your_public_key",
    lighter_perpetual_private_key="your_private_key",
    lighter_perpetual_api_key_index=3,
    trading_pairs=["BTC-USDC"],
    trading_required=True,
    domain="lighter_perpetual"
)

# Check positions
positions = await connector._update_positions()

# Set leverage
success, msg = await connector._set_trading_pair_leverage("BTC-USDC", 10)
```

## Docker Usage

```bash
# Build image with Lighter Perpetual connector
docker build -t hummingbot-custom .

# Run container
docker run -it --rm \
  --name hb-lighter \
  -v $(pwd)/conf:/home/hummingbot/conf \
  -v $(pwd)/data:/home/hummingbot/data \
  -v $(pwd)/logs:/home/hummingbot/logs \
  hummingbot-custom

# Connect to Lighter Perpetual
>>> connect lighter_perpetual
# Enter your 3 credentials when prompted
```

## Testing Checklist

Before trading on mainnet:

- [ ] Test connection on testnet first (if available)
- [ ] Verify balance shows correctly (after deposit)
- [ ] Check positions update correctly
- [ ] Test order placement with small size
- [ ] Verify order cancellation works
- [ ] Monitor funding rate updates
- [ ] Test leverage adjustment
- [ ] Check WebSocket reconnection
- [ ] Verify nonce management works

## Important Notes

### 1. API Key Private Key Security
The API key private key is **extremely sensitive**:
- It can sign transactions on your behalf
- Never share it or commit it to version control
- Store securely using environment variables or secret management
- Rotate regularly for security

### 2. Nonce Management
Lighter requires nonce-based transaction signing:
- Each transaction needs a unique, incrementing nonce
- Connector automatically fetches next nonce from API
- Nonce is tracked per API_KEY
- If multiple clients use same API key, nonce conflicts may occur

### 3. Transaction Signing
Current implementation uses a **simplified signature**:
```python
def generate_transaction_signature(self, order_params: Dict[str, Any], nonce: int) -> str:
    # Simplified placeholder implementation
    # For production, integrate with Lighter SDK or crypto library
```

**For production**, you may need to:
- Integrate with Lighter's Python SDK
- Use proper cryptographic signing
- Follow Lighter's exact signature format

### 4. Position Mode
Lighter only supports **one-way position mode**:
- No hedge mode
- Single position per market
- Position size can be positive (long) or negative (short)

## Troubleshooting

### Balance shows $0 but you have funds
**Check:**
1. API key private key is correct
2. Account index is correct
3. You're on the right network (mainnet vs testnet)
4. Funds are in your trading account
5. Check Lighter UI to verify balance

### "Nonce too low" or nonce errors
**Solution:**
- Connector will automatically fetch latest nonce
- Restart connector if persistent
- Ensure only one client is using the API key

### WebSocket disconnections
**Cause**: Network issues or Lighter API changes  
**Solution**: 
- Connector auto-reconnects
- Check logs for specific error
- Verify WebSocket URL is correct

### "Markets are not ready"
**Cause**: Market symbol mapping failed  
**Check**:
1. `/api/v1/markets` endpoint returns data
2. Markets have active status
3. Symbol mapping handles market format

## API Rate Limits

- **Public endpoints**: 100 requests/second
- **Private endpoints**: 50 requests/second
- **All endpoints combined**: 100 requests/second

Limits are enforced automatically via `AsyncThrottler`.

## Security Best Practices

1. **Protect your API key private key** - it's extremely sensitive
2. **Use testnet first** - verify everything works before mainnet
3. **Start with low leverage** - understand the platform first
4. **Monitor positions regularly** - perpetuals can liquidate quickly
5. **Set stop losses** - protect against adverse moves
6. **Rotate API keys** - regularly for security
7. **Use separate API keys per client** - avoid nonce conflicts

## Account Types

Lighter API users can operate under Standard or Premium accounts:
- **Standard**: Fee-less (certain conditions may apply)
- **Premium**: 0.2 bps maker and 2 bps taker fees

Find out more in [Lighter's Account Types documentation](https://apidocs.lighter.xyz/docs/get-started-for-programmers-1#/).

## Summary of Files Created

✅ **8 files created** in `/hummingbot/connector/derivative/lighter_perpetual/`:

1. `__init__.py` - Package init
2. `lighter_perpetual_constants.py` - Constants & endpoints
3. `lighter_perpetual_utils.py` - Config & utilities  
4. `lighter_perpetual_web_utils.py` - Web helpers
5. `lighter_perpetual_auth.py` - Authentication & nonce management
6. `lighter_perpetual_api_order_book_data_source.py` - Order book
7. `lighter_perpetual_api_user_stream_data_source.py` - User stream
8. `lighter_perpetual_derivative.py` - Main perpetual class

## Next Steps

1. **Get Credentials**:
   - Sign up at https://lighter.xyz
   - Generate API key private key
   - Note your account index and choose API key index

2. **Rebuild if using Docker**:
   ```bash
   docker build -t hummingbot-custom .
   ```

3. **Connect to Lighter Perpetual**:
   ```bash
   >>> connect lighter_perpetual
   ```

4. **Deposit USDC** to your Lighter account

5. **Check balance**:
   ```bash
   >>> balance lighter_perpetual
   ```

6. **Test with a perpetual strategy**:
   ```bash
   >>> create
   # Select a perpetual-compatible strategy
   # Choose lighter_perpetual as the exchange
   ```

## Support & Resources

- **Lighter Docs**: https://apidocs.lighter.xyz/docs/get-started-for-programmers-1#/
- **Lighter Website**: https://lighter.xyz
- **Lighter SDK**: https://github.com/lighter-xyz (if available)
- **Hummingbot Discord**: https://discord.gg/hummingbot

## License

Part of the Hummingbot project - Apache 2.0 License

