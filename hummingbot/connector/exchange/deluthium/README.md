# Deluthium DEX Connector

Deluthium (DarkPool) is an RFQ-based decentralized exchange that provides swap quotes and on-chain execution across multiple EVM chains.

## Supported Chains

| Chain | Chain ID | Native Token |
|-------|----------|--------------|
| BSC | 56 | BNB |
| Base | 8453 | ETH |
| Ethereum | 1 | ETH |

## Features

- **RFQ-Based Trading**: Request for Quote model for optimal pricing
- **Multi-Chain Support**: Trade across BSC, Base, and Ethereum
- **JWT Authentication**: Secure API access with pre-issued JWT tokens
- **Indicative Quotes**: Get price estimates before committing to trades
- **Firm Quotes**: Receive calldata for on-chain execution

## Configuration

### Required Credentials

| Parameter | Description |
|-----------|-------------|
| `deluthium_api_key` | JWT token from Deluthium team |
| `deluthium_chain_id` | Chain ID (56, 8453, or 1) |
| `deluthium_wallet_address` | Your wallet address for RFQ quotes |

### How to Get API Access

1. Contact the Deluthium team at [https://deluthium.ai](https://deluthium.ai)
2. Provide your company information
3. Receive your JWT token

## Usage

### Connect to Deluthium

```python
connect deluthium
```

When prompted, enter:
- Your JWT token
- Chain ID (56 for BSC, 8453 for Base, 1 for Ethereum)
- Your wallet address (optional)

### Example Strategy Configuration

```yaml
exchange: deluthium
trading_pair: WBNB-USDT
```

## Important Notes

### RFQ Trading Model

Deluthium uses a Request for Quote (RFQ) model:

1. **Indicative Quote**: Get an estimated price (non-binding)
2. **Firm Quote**: Get a binding quote with calldata
3. **On-Chain Execution**: User broadcasts the transaction

**Hummingbot does NOT broadcast transactions.** The firm quote response contains:
- `calldata`: Transaction data to submit on-chain
- `router_address`: Contract address to call
- `deadline`: Quote expiration timestamp

You must use a separate wallet/signer to execute the calldata on-chain.

### Order Types

Only **market orders** are supported (RFQ-based). Limit orders are not available.

### Order Cancellation

RFQ orders cannot be cancelled. They either:
- Get executed on-chain before the deadline
- Expire automatically after the deadline

### Amounts in Wei

All amounts in the API are in wei format (integer strings). The connector handles conversion automatically.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/v1/listing/pairs` | Get supported trading pairs |
| `/v1/listing/tokens` | Get supported tokens |
| `/v1/market/pair` | Get market overview for a pair |
| `/v1/market/klines` | Get candlestick/OHLCV data |
| `/v1/quote/indicative` | Get indicative quote |
| `/v1/quote/firm` | Get firm quote with calldata |

## Error Codes

### Trading Service (String Codes)

| Code | Description |
|------|-------------|
| `INVALID_INPUT` | Request field missing or invalid |
| `INVALID_TOKEN` | Token address not supported |
| `MM_NOT_AVAILABLE` | Market maker not available |
| `SLIPPAGE_EXCEEDED` | Slippage tolerance exceeded |

### Market Data Service (Numeric Codes)

| Code | Description |
|------|-------------|
| 10000 | Success |
| 10095 | Invalid parameters |
| 20003 | Internal service error |
| 20004 | Not found (e.g., pair not found) |

## Support

For issues with:
- **API Access**: Contact Deluthium team
- **Hummingbot Integration**: Open an issue on GitHub

## License

Apache 2.0
