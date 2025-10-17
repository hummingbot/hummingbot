# Extended Exchange Connector for Hummingbot

## Overview

This connector integrates Extended Exchange (https://extended.exchange) with Hummingbot, enabling perpetual trading on their Starknet-based DEX platform.

## Connector Structure

The Extended connector follows the same framework as the Asterdex connector with the following files:

```
hummingbot/connector/exchange/extended/
├── __init__.py                              # Package initialization
├── extended_constants.py                    # API endpoints, rate limits, and constants
├── extended_utils.py                        # Utility functions and config
├── extended_web_utils.py                    # Web assistant utilities
├── extended_auth.py                         # Authentication handler
├── extended_api_order_book_data_source.py  # Order book data source
├── extended_api_user_stream_data_source.py # User stream data source
└── extended_exchange.py                     # Main exchange class
```

## Key Features

### API Endpoints (Starknet Mainnet)
- **REST API**: `https://api.starknet.extended.exchange/api/v1/`
- **WebSocket**: `wss://api.starknet.extended.exchange/stream.extended.exchange/v1`

### Supported Functionality
- ✅ Real-time order book data via WebSocket
- ✅ Account balance tracking
- ✅ Order placement (Market, Limit, Limit Maker)
- ✅ Order cancellation
- ✅ Trade execution and fills
- ✅ Position management (for perpetuals)
- ✅ Fee tracking
- ✅ User stream for account updates

### Trading Features
- **Order Types**: Market, Limit, Limit Maker (Post-Only)
- **Collateral**: USDC
- **Leverage**: Up to 100x
- **Markets**: Crypto and TradFi perpetuals

## Configuration

### API Credentials

You'll need to obtain API credentials from Extended Exchange:

1. Visit https://extended.exchange
2. Create an account
3. Navigate to API settings
4. Generate the following credentials:
   - **API Key** - Required for all API requests
   - **Stark Public Key** - Required for order signing
   - **Stark Private Key** - Used to generate signatures

**Note:** Vault Number and Client ID are NOT needed for API access (they're only for sub-account management).

### Connector Setup

To use the Extended connector in Hummingbot:

```python
# In your strategy configuration
connector: extended
extended_api_key: YOUR_API_KEY
extended_stark_public_key: YOUR_STARK_PUBLIC_KEY
extended_stark_private_key: YOUR_STARK_PRIVATE_KEY
```

### Configuration File Structure

The connector configuration is defined in `extended_utils.py`:

```python
class ExtendedConfigMap(BaseConnectorConfigMap):
    connector: str = "extended"
    extended_api_key: SecretStr  # Your Extended API key
    extended_stark_public_key: SecretStr  # Your Stark public key
    extended_stark_private_key: SecretStr  # Your Stark private key
```

## API Documentation

Extended's full API documentation: https://api.docs.extended.exchange/

### Key Endpoints Used

#### Public Endpoints
- `GET /markets` - Get all available markets
- `GET /markets/statistics` - Get market statistics
- `GET /markets/orderbook` - Get order book snapshot
- `GET /markets/trades` - Get recent trades
- `GET /markets/funding-rates` - Get funding rates
- `GET /markets/candles` - Get price candles

#### Private Endpoints
- `GET /account` - Get account details
- `GET /account/balance` - Get account balance
- `GET /account/positions` - Get open positions
- `GET /account/orders/open` - Get open orders
- `POST /account/orders` - Create new order
- `DELETE /account/orders/{order_id}` - Cancel order
- `GET /account/trades` - Get trade history
- `GET /account/fees` - Get fee rates

### WebSocket Channels

#### Public Channels
- `orderbook` - Real-time order book updates
- `trades` - Real-time trade feed
- `funding-rates` - Funding rate updates
- `mark-price` - Mark price updates
- `index-price` - Index price updates

#### Private Channels
- `account-updates` - Account events (orders, positions, balance)

## Authentication

Extended uses Starknet signature-based authentication:

1. **REST API**: 
   - API key in `X-Api-Key` header (all requests)
   - Stark signature in request body (order management only)
   - Stark public key in request body (order management only)
   
2. **WebSocket**:
   - API key in `X-Api-Key` header
   
3. **Order Signing**:
   - Orders require Stark signatures generated using your Stark private key
   - Signatures follow the Starknet signing standard (SNIP12)
   - The signature and public key are included in order placement requests

The authentication is handled automatically by `extended_auth.py`.

**Important:** The current implementation includes a placeholder for Stark signature generation. For production use, you may need to implement proper Starknet signature generation using the `starkware-crypto` library.

## Rate Limits

Default rate limits (can be adjusted based on your account tier):

- **Public endpoints**: 100 requests per second
- **Private endpoints**: 50 requests per second
- **All endpoints combined**: 100 requests per second

Rate limits are enforced via the `AsyncThrottler` in `extended_web_utils.py`.

## Trading Fees

Default fees (actual fees may vary by account):
- **Maker Fee**: 0.02% (0.0002)
- **Taker Fee**: 0.05% (0.0005)

Fees are automatically fetched from the `/account/fees` endpoint.

## Order States Mapping

Extended order states are mapped to Hummingbot's OrderState:

| Extended Status | Hummingbot State |
|----------------|------------------|
| pending        | PENDING_CREATE   |
| open           | OPEN            |
| filled         | FILLED          |
| partially_filled | PARTIALLY_FILLED |
| cancelled      | CANCELED        |
| rejected       | FAILED          |
| expired        | CANCELED        |

## Market ID Format

Extended uses hyphenated market IDs:
- Format: `{BASE}-{QUOTE}` (e.g., `BTC-USDC`, `ETH-USDC`)
- Hummingbot format: `{BASE}-{QUOTE}` (same as Extended)

## Example Usage

### Basic PMM Strategy

```yaml
# conf_pmm_extended.yml
exchange: extended
market: BTC-USDC
bid_spread: 0.5
ask_spread: 0.5
order_amount: 0.01
```

### In Python Script

```python
from hummingbot.connector.exchange.extended.extended_exchange import ExtendedExchange

# Initialize connector
connector = ExtendedExchange(
    extended_api_key="your_api_key",
    extended_stark_public_key="your_stark_public_key",
    extended_stark_private_key="your_stark_private_key",
    trading_pairs=["BTC-USDC"],
    trading_required=True
)

# Get markets
markets = await connector.get_all_pairs_prices()

# Place order
order_id = await connector._place_order(
    order_id="custom_order_123",
    trading_pair="BTC-USDC",
    amount=Decimal("0.01"),
    trade_type=TradeType.BUY,
    order_type=OrderType.LIMIT,
    price=Decimal("50000")
)
```

## Testing

Before using in production:

1. **Test on Extended Testnet**:
   - Update URLs in `extended_constants.py` to testnet endpoints
   - Testnet URL: `https://api.starknet.sepolia.extended.exchange/api/v1`
   - Testnet WebSocket: `wss://starknet.sepolia.extended.exchange/stream.extended.exchange/v1`

2. **Verify Connection**:
   ```bash
   # Test API connection
   curl -H "API-KEY: your_key" https://api.starknet.extended.exchange/api/v1/markets
   ```

3. **Test Small Orders**: Start with small amounts to verify order placement and fills

## Migration from StarkEx to Starknet

Extended is migrating from StarkEx to Starknet. This connector is built for the **Starknet instance**:

- **Current**: Starknet mainnet
- **URL**: `api.starknet.extended.exchange`
- **Supported wallets**: EVM and Starknet wallets
- **Signing**: SNIP12 standard (EIP712 for Starknet)

If you need StarkEx support, refer to Extended's legacy documentation.

## Troubleshooting

### Common Issues

1. **"Markets are not ready"**
   - Check if trading pairs are correctly formatted (e.g., `BTC-USDC`)
   - Verify market_id exists on Extended
   - Check `_initialize_trading_pair_symbols_from_exchange_info()` mapping

2. **Authentication Errors**
   - Verify API key and secret are correct
   - Check timestamp synchronization
   - Ensure API key has required permissions

3. **WebSocket Connection Issues**
   - Verify WebSocket URL is accessible
   - Check network/firewall settings
   - Review authentication headers for private channels

4. **Order Placement Failures**
   - Verify sufficient balance
   - Check order size meets minimum requirements
   - Ensure price is within tick size constraints

### Debug Logging

Enable debug logging to troubleshoot:

```python
# In your strategy or script
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Additional Resources

- **Extended Documentation**: https://docs.extended.exchange/
- **Extended API Docs**: https://api.docs.extended.exchange/
- **Extended Vision**: https://docs.extended.exchange/about-extended/vision-and-roadmap
- **Discord Support**: https://discord.com/channels/1193905940076953660/1214882006475997244

## Differences from Asterdex Connector

While following the same framework, Extended differs in:

1. **Market Format**: Uses hyphenated format (BTC-USDC) vs no separator (BTCUSDC)
2. **Authentication**: Different header names (API-KEY vs X-MBX-APIKEY)
3. **WebSocket Protocol**: Different message structure and channels
4. **Order Response**: Different response format for order placement
5. **Perpetuals Focus**: Built for perpetual contracts vs spot trading

## Support

For issues or questions:

1. Check Extended's API documentation
2. Review connector logs for error details
3. Test on Extended's testnet first
4. Contact Extended support via Discord

## License

This connector is part of the Hummingbot project and follows the same Apache 2.0 license.

