# Hyperliquid Perpetual Connector

This document provides instructions for connecting to the Hyperliquid Perpetual exchange using Hummingbot, supporting both API key and wallet private key authentication.

## Configuration

To configure the Hyperliquid Perpetual connector, you need to provide your credentials. You can choose between two authentication methods:

1.  **API Key Authentication (Recommended)**: Use an API key and API secret generated from the Hyperliquid website.
2.  **Wallet Private Key Authentication**: Use your Arbitrum wallet private key and address.

### API Key Authentication

1.  **`hyperliquid_perpetual_api_key`**: Enter your Hyperliquid Perpetual API key.
2.  **`hyperliquid_perpetual_api_secret`**: Enter your Hyperliquid Perpetual API secret.

Example configuration:

```yaml
connector:
  hyperliquid_perpetual:
    hyperliquid_perpetual_api_key: "YOUR_API_KEY"
    hyperliquid_perpetual_api_secret: "YOUR_API_SECRET"
    use_vault: "no"
```

### Wallet Private Key Authentication

1.  **`wallet_address`**: Enter your Arbitrum wallet address.
2.  **`wallet_private_key`**: Enter your Arbitrum wallet private key.

Example configuration:

```yaml
connector:
  hyperliquid_perpetual:
    wallet_address: "YOUR_WALLET_ADDRESS"
    wallet_private_key: "YOUR_PRIVATE_KEY"
    use_vault: "no"
```

**Note**: You should only provide credentials for one authentication method. If both are provided, API Key Authentication will take precedence.

## Trading Pairs

Example trading pair: `BTC-USD`
