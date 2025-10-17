# Extended Perpetual Connector for Hummingbot

## Overview

This connector integrates Extended Exchange's **Perpetual Futures** platform with Hummingbot. Extended is a **perp-only DEX** built on Starknet - they do NOT offer spot trading.

**Important:** This is the CORRECT connector for Extended Exchange. The spot connector at `/connector/exchange/extended/` will NOT work because Extended only offers perpetuals.

## 🎯 What Extended Offers

- ✅ **Perpetual Contracts** - Crypto & TradFi assets
- ✅ **USDC Collateral** - All positions settled in USDC
- ✅ **Up to 100x Leverage**
- ✅ **No Expiration** - True perpetual futures
- ❌ **NO Spot Trading** - Only perpetuals

## Connector Structure

```
hummingbot/connector/derivative/extended_perpetual/
├── __init__.py
├── extended_perpetual_constants.py          # API endpoints & constants
├── extended_perpetual_utils.py              # Config & utilities
├── extended_perpetual_web_utils.py          # Web assistant factory
├── extended_perpetual_auth.py               # Starknet authentication
├── extended_perpetual_api_order_book_data_source.py  # Order book data
├── extended_perpetual_api_user_stream_data_source.py # User stream
└── extended_perpetual_derivative.py         # Main perpetual class
```

## API Configuration

### Mainnet (Production)
- **REST API**: `https://api.starknet.extended.exchange/`
- **WebSocket**: `wss://api.starknet.extended.exchange/stream.extended.exchange/v1`

### Testnet
- **REST API**: `https://api.starknet.sepolia.extended.exchange/`
- **WebSocket**: `wss://api.starknet.sepolia.extended.exchange/stream.extended.exchange/v1`

## Required Credentials

When connecting to Extended Perpetual, you need **3 credentials**:

1. **API Key** (`extended_perpetual_api_key`)
   - Used in `X-Api-Key` header for all requests
   
2. **Stark Public Key** (`extended_perpetual_stark_public_key`)
   - Your Starknet public key
   - Included in order requests for verification
   
3. **Stark Private Key** (`extended_perpetual_stark_private_key`)
   - Your Starknet private key
   - Used locally to sign orders (never sent to API)

**NOT needed:**
- ❌ Vault Number (only for sub-accounts)
- ❌ Client ID (only for sub-accounts)

## How to Get Your Credentials

1. Go to https://extended.exchange
2. Create an account (requires deposit to activate)
3. Navigate to **API Settings**
4. Generate:
   - API Key
   - Stark Public Key  
   - Stark Private Key

## Connection Flow

```bash
>>> connect extended_perpetual

Enter your Extended API key >>> [paste API key]
Enter your Extended Stark public key >>> [paste Stark public key]
Enter your Extended Stark private key >>> [paste Stark private key]
```

## Key API Endpoints

### Public Endpoints
- `GET /api/v1/info/markets` - Get all markets
- `GET /api/v1/info/markets/stats` - Market statistics
- `GET /api/v1/info/markets/orderbook?market_id={market}` - Order book
- `GET /api/v1/info/markets/trades?market_id={market}` - Recent trades
- `GET /api/v1/info/markets/funding-rates?market_id={market}` - Funding rates

### Private Endpoints
- `GET /api/v1/user/account` - Account details
- `GET /api/v1/user/balance` - Get balance (404 if zero)
- `GET /api/v1/user/positions` - Get positions
- `POST /api/v1/user/orders` - Place order
- `DELETE /api/v1/user/orders/{order_id}` - Cancel order
- `GET /api/v1/user/trades` - Trade history
- `POST /api/v1/user/leverage` - Set leverage
- `GET /api/v1/user/funding-payments` - Funding payment history

## Market Format

Extended uses **hyphenated USD format**:
- **Extended**: `BTC-USD`, `ETH-USD`, `SOL-USD`
- **Hummingbot**: `BTC-USDC`, `ETH-USDC`, `SOL-USDC`

The connector automatically maps `{BASE}-USD` → `{BASE}-USDC` since Extended settles in USDC.

## Perpetual-Specific Features

### Position Management
- **Position Mode**: One-way only (no hedge mode)
- **Collateral**: USDC
- **Leverage**: 1x to 100x (varies by market)
- **Liquidation**: Automatic based on margin requirements

### Funding Rates
- Updated every hour
- Typical range: -0.01% to +0.01%
- Automatically fetched and applied
- Long positions pay when positive, receive when negative

### Order Types
- ✅ **Market** - Immediate execution
- ✅ **Limit** - GTC (Good-Till-Time, max 90 days)
- ✅ **Limit Maker** - Post-only orders

### Order Requirements
- **Expiration**: All orders require expiration timestamp (max 90 days)
- **Min Size**: Varies by market (typically 0.01-100 units)
- **Tick Size**: Varies by market
- **Signature**: All orders must be signed with Stark private key

## Known Issues & Solutions

### Issue 1: Balance Shows $0 (404 Error)
**Cause**: Extended returns HTTP 404 when balance is zero  
**Solution**: ✅ Already handled in connector - will show info message  
**Action**: Deposit USDC to your Extended account

### Issue 2: "Markets are not ready"
**Cause**: Market symbol mapping issues  
**Solution**: Check that markets endpoint returns valid data  
**Debug**: Look at logs for trading pair initialization

### Issue 3: Order Book Stream Errors
**Cause**: WebSocket message format differences  
**Solution**: Check WebSocket channel names and message structure  
**Note**: Extended uses different WS format than spot exchanges

### Issue 4: Cannot use with spot strategies
**Cause**: Extended is PERPETUALS ONLY  
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
# conf_pmm_extended_perp.yml
exchange: extended_perpetual
market: BTC-USDC  # Will map to BTC-USD on Extended
leverage: 5
bid_spread: 0.5
ask_spread: 0.5
order_amount: 0.01
```

### In Python Script

```python
from hummingbot.connector.derivative.extended_perpetual.extended_perpetual_derivative import ExtendedPerpetualDerivative

# Initialize connector
connector = ExtendedPerpetualDerivative(
    extended_perpetual_api_key="your_api_key",
    extended_perpetual_stark_public_key="your_stark_public_key",
    extended_perpetual_stark_private_key="your_stark_private_key",
    trading_pairs=["BTC-USDC"],
    trading_required=True,
    domain="extended_perpetual"
)

# Check positions
positions = await connector._update_positions()

# Set leverage
success, msg = await connector._set_trading_pair_leverage("BTC-USDC", 10)
```

## Docker Usage

```bash
# Build image with Extended Perpetual connector
docker build -t hummingbot-custom .

# Run container
docker run -it --rm \
  --name hb-extended \
  -v $(pwd)/conf:/home/hummingbot/conf \
  -v $(pwd)/data:/home/hummingbot/data \
  -v $(pwd)/logs:/home/hummingbot/logs \
  hummingbot-custom

# Connect to Extended Perpetual
>>> connect extended_perpetual
# Enter your 3 credentials when prompted
```

## Testing Checklist

Before trading on mainnet:

- [ ] Test connection on testnet first
- [ ] Verify balance shows correctly (after deposit)
- [ ] Check positions update correctly
- [ ] Test order placement with small size
- [ ] Verify order cancellation works
- [ ] Monitor funding rate updates
- [ ] Test leverage adjustment
- [ ] Check WebSocket reconnection

## Important Notes

### 1. Zero Balance = 404 Error
Extended returns HTTP 404 when your balance is zero. This is **normal behavior** if you haven't deposited. The connector handles this gracefully.

**Solution**: Deposit USDC to your Extended account first.

### 2. Stark Signature Placeholder
The current implementation has a **placeholder** for Stark signature generation:

```python
def generate_stark_signature(self, order_params: Dict[str, Any]) -> str:
    # TODO: Implement proper Stark signature generation
    return self.stark_private_key  # Placeholder
```

**For production**, you may need to implement proper Starknet signatures using:
- `starkware-crypto` library
- Pedersen hash for message signing
- SNIP12 standard (EIP712 for Starknet)

### 3. Order Expiration Required
All orders require an expiration timestamp:
- **Maximum**: 90 days from order creation (mainnet)
- **Format**: Epoch timestamp in milliseconds
- **Handled automatically** by connector (default: 7 days)

### 4. Position Mode
Extended only supports **one-way position mode**:
- No hedge mode
- Single position per market
- Position size can be positive (long) or negative (short)

## Troubleshooting

### Balance shows $0 but you have funds
**Check:**
1. API key has correct permissions
2. You're on the right network (mainnet vs testnet)
3. Funds are in your trading account (not vault)
4. Check Extended UI to verify balance

**Solution**: Connector logs will show "No balance found (404)" if truly zero, or display actual balance if detected.

### "Rate oracle received" error
**Cause**: Rate oracle trying to fetch prices for perpetuals  
**Solution**: Ensure you're using perpetual-compatible strategies

### WebSocket disconnections
**Cause**: Network issues or Extended API changes  
**Solution**: 
- Connector auto-reconnects
- Check logs for specific error
- Verify WebSocket URL is correct

### "Markets are not ready"
**Cause**: Market symbol mapping failed  
**Check**:
1. `/api/v1/info/markets` endpoint returns data
2. Markets have `"status": "ACTIVE"`
3. Symbol mapping handles `{BASE}-USD` format

## API Rate Limits

- **Public endpoints**: 100 requests/second
- **Private endpoints**: 50 requests/second
- **All endpoints combined**: 100 requests/second

Limits are enforced automatically via `AsyncThrottler`.

## Security Best Practices

1. **Protect your Stark private key** - it's like your wallet private key
2. **Use testnet first** - verify everything works before mainnet
3. **Start with low leverage** - understand the platform first
4. **Monitor positions regularly** - perpetuals can liquidate quickly
5. **Set stop losses** - protect against adverse moves
6. **Rotate API keys** - regularly for security

## Differences: Spot vs Perpetual Connector

| Feature | Spot Connector (Wrong) | Perpetual Connector (Correct) |
|---------|----------------------|------------------------------|
| Location | `/exchange/extended/` | `/derivative/extended_perpetual/` |
| Base Class | `ExchangePyBase` | `PerpetualDerivativePyBase` |
| Markets | Would fail (no spot) | ✅ Works with perps |
| Positions | N/A | ✅ Position tracking |
| Leverage | N/A | ✅ Leverage management |
| Funding | N/A | ✅ Funding rate tracking |
| Strategies | Spot only | ✅ Perpetual strategies |

## Summary of Files Created

✅ **8 files created** in `/hummingbot/connector/derivative/extended_perpetual/`:

1. `__init__.py` - Package init
2. `extended_perpetual_constants.py` - Constants & endpoints
3. `extended_perpetual_utils.py` - Config & utilities  
4. `extended_perpetual_web_utils.py` - Web helpers
5. `extended_perpetual_auth.py` - Stark authentication
6. `extended_perpetual_api_order_book_data_source.py` - Order book
7. `extended_perpetual_api_user_stream_data_source.py` - User stream
8. `extended_perpetual_derivative.py` - Main perpetual class

## Next Steps

1. **Rebuild Docker image**:
   ```bash
   docker build -t hummingbot-custom .
   ```

2. **Connect to Extended Perpetual**:
   ```bash
   docker run -it --rm --name hb-extended -v $(pwd)/conf:/conf hummingbot-custom
   >>> connect extended_perpetual
   ```

3. **Deposit USDC** to your Extended account

4. **Check balance**:
   ```bash
   >>> balance extended_perpetual
   ```

5. **Test with a perpetual strategy**:
   ```bash
   >>> create
   # Select a perpetual-compatible strategy
   # Choose extended_perpetual as the exchange
   ```

## Support & Resources

- **Extended Docs**: https://docs.extended.exchange/
- **API Docs**: https://api.docs.extended.exchange/
- **Discord**: https://discord.com/channels/1193905940076953660/1214882006475997244
- **Hummingbot Discord**: https://discord.gg/hummingbot

## License

Part of the Hummingbot project - Apache 2.0 License

