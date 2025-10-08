# Hyperliquid Perpetual Connector

This connector allows Hummingbot to interact with the Hyperliquid decentralized exchange for perpetual futures trading.

## Configuration

The Hyperliquid Perpetual connector supports three authentication modes:

### 1. Wallet Mode (Default)
Connect using your main Arbitrum wallet private key:
- **hyperliquid_perpetual_api_secret**: Your Arbitrum wallet private key
- **hyperliquid_perpetual_api_key**: Your Arbitrum wallet address
- **use_vault**: No
- **use_api_wallet**: No

### 2. Vault Mode
For trading through Hyperliquid vaults:
- **hyperliquid_perpetual_api_secret**: Your Arbitrum wallet private key
- **hyperliquid_perpetual_api_key**: The vault address (can include "HL:" prefix which will be stripped)
- **use_vault**: Yes
- **use_api_wallet**: No

### 3. API Wallet Mode (Recommended for Security)
Use API credentials created through the Hyperliquid web interface:
- **hyperliquid_perpetual_api_secret**: Your API wallet private key
- **hyperliquid_perpetual_api_key**: Your main Arbitrum wallet address (NOT the API wallet address)
- **use_vault**: No
- **use_api_wallet**: Yes

## Setting up API Wallet (Recommended)

API wallets provide enhanced security by allowing trading without exposing your main wallet's private key.

### Steps to create an API wallet:

1. Visit [https://app.hyperliquid.xyz/API](https://app.hyperliquid.xyz/API)
2. Connect your main wallet
3. Generate a new API key
4. Copy the generated API wallet private key
5. Configure Hummingbot with:
   - API wallet private key as `hyperliquid_perpetual_api_secret`
   - Your main wallet address as `hyperliquid_perpetual_api_key`
   - Set `use_api_wallet` to `Yes`

### Benefits of API Wallets:
- **Enhanced Security**: Main wallet private key stays secure
- **Trading Permissions**: API wallet can trade but cannot withdraw funds
- **Audit Trail**: Better tracking of automated trading activity
- **Risk Management**: Limited exposure if API credentials are compromised

## Configuration Examples

### Example 1: API Wallet Configuration
```
use_vault: No
use_api_wallet: Yes
hyperliquid_perpetual_api_secret: 0x1234567890abcdef...  # API wallet private key
hyperliquid_perpetual_api_key: 0xabcdef1234567890...     # Main wallet address
```

### Example 2: Vault Configuration
```
use_vault: Yes
use_api_wallet: No
hyperliquid_perpetual_api_secret: 0x1234567890abcdef...  # Main wallet private key
hyperliquid_perpetual_api_key: HL:0xdef123456789abc...   # Vault address (HL: prefix optional)
```

### Example 3: Direct Wallet Configuration
```
use_vault: No
use_api_wallet: No
hyperliquid_perpetual_api_secret: 0x1234567890abcdef...  # Main wallet private key
hyperliquid_perpetual_api_key: 0x1234567890abcdef...     # Main wallet address
```

## Testnet Support

The connector also supports Hyperliquid testnet through the `hyperliquid_perpetual_testnet` domain. Configuration follows the same pattern with testnet-specific parameter names.

## Features

- **Perpetual Futures Trading**: Full support for perpetual contracts on Hyperliquid
- **Leverage Trading**: Support for leveraged positions
- **Order Types**: Market and limit orders with various time-in-force options
- **Position Management**: Real-time position tracking and management
- **Real-time Data**: Order book, trades, funding rates, and account updates via WebSocket
- **Ed25519 Signing**: Native support for Hyperliquid's signing requirements
- **Multi-mode Authentication**: Wallet, vault, and API wallet support

## Important Notes

- When using API wallets, ensure you use your **main wallet address** (not the API wallet address) as the `api_key`
- The API wallet private key is used for signing, but the main wallet address is used for account identification
- API wallets cannot withdraw funds, providing an additional security layer
- Vault addresses can include the "HL:" prefix, which will be automatically stripped
- Perpetual trading involves additional risks including liquidation - ensure proper risk management

## Risk Management

When trading perpetuals on Hyperliquid:
- Monitor margin requirements and liquidation prices
- Use appropriate position sizing
- Set stop-loss orders where appropriate
- Understand funding rate implications
- Be aware of leverage effects on P&L

## Troubleshooting

1. **Authentication Errors**: Verify that you're using the correct combination of addresses and keys for your chosen mode
2. **API Wallet Issues**: Ensure the API wallet private key matches the key generated on the Hyperliquid website
3. **Vault Problems**: Check that the vault address is correct and you have the necessary permissions
4. **Position Issues**: Verify margin requirements and ensure sufficient collateral
5. **Testnet Connection**: Make sure you're using testnet credentials when connecting to testnet

For additional support, refer to the Hummingbot documentation or Hyperliquid's official documentation at [https://hyperliquid.gitbook.io/](https://hyperliquid.gitbook.io/).