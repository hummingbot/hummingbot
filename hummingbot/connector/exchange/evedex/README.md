# EVEDEX Connector

This connector integrates [EVEDEX](https://evedex.com), a decentralized perpetual futures exchange, with Hummingbot.

## Features

- **Perpetual Futures Trading**: Full support for EVEDEX perpetual contracts
- **EIP-712 Authentication**: Secure wallet-based signing for all authenticated requests
- **Real-time WebSocket**: Order book, trades, and user stream via Centrifuge protocol
- **Position Management**: One-way position mode support

## Configuration

| Parameter | Description |
|-----------|-------------|
| `evedex_private_key` | Your Ethereum private key (hex format with 0x prefix) |

## Authentication

EVEDEX uses EIP-712 typed data signing for authentication. The connector:

1. Signs requests using the configured private key
2. Authenticates to the WebSocket using SIWE (Sign-In with Ethereum) for user streams
3. Derives the wallet address automatically from the private key

## API Endpoints

| Type | URL |
|------|-----|
| REST | `https://trading-api.evedex.com` |
| Auth | `https://auth-api.evedex.com` |
| WebSocket | `wss://ws.evedex.com/connection/websocket` |

## WebSocket Channels

Channels use the Centrifuge protocol with prefix `futures-perp`:

- `futures-perp:order_book:{instrument}` - Order book updates
- `futures-perp:trades:{instrument}` - Trade stream
- Private channels (with auth token): `orders`, `positions`, `balance`, `fills`

## Supported Order Types

- Limit orders (GTC)
- Market orders

## References

- [EVEDEX Trading SDK](https://github.com/evedex-official/exchange-bot-sdk)
- [EVEDEX API Documentation](https://swagger.evedex.com/?urls.primaryName=Exchange)
- [EVEDEX Docs](https://docs.evedex.com/)

## Development Notes

Chain ID for EIP-712 signing: `161803` (Production)
