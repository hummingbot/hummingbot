# Decibel Perpetual Connector (Aptos)

The Decibel connector allows users to provide liquidity and trade on the Decibel Perpetual exchange, a high-performance CLOB built on the Aptos blockchain.

## 📁 Connector Info

*   **Connector Type:** Derivative / Perpetual
*   **Exchange Name:** `decibel_perpetual`
*   **Aptos Network:** Mainnet (Default) / Testnet
*   **Base Asset:** USDC

## 🔑 Prerequisites

1.  **Aptos Wallet:** You need an Aptos account with sufficient APT for gas fees.
2.  **USDC Balance:** Trading on Decibel requires USDC on Aptos.
3.  **API Key:** Interaction with the Decibel trading endpoints may require an API key from Aptos Labs / Decibel Team (see configuration).

## ⚙️ Configuration

To use the Decibel connector, you need to configure the following parameters in Hummingbot:

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `decibel_perpetual_private_key` | secret | Your Aptos account private key (hex string). |
| `decibel_perpetual_api_key` | secret | Optional: API key for the trading upstream. |
| `decibel_perpetual_subaccount_index` | int | Default: `0`. Use specific subaccount if needed. |

## 📊 Trading Rules

The connector automatically fetches trading rules from the Decibel metadata.

*   **Min Order Size:** Varies per market (typically 0.01 BTC / 0.1 ETH).
*   **Price Increments:** Based on `tick_size` provided by the on-chain config.
*   **Leverage:** Supported leverage depends on market risk parameters (up to 20x).

## ⛓️ Aptos Integration Details

Decibel uses a high-frequency off-chain orderbook with on-chain settlement on Aptos. 

### Subaccounts
The connector supports Decibel's subaccount architecture. Each private key can manage multiple subaccounts. The connector defaults to the primary subaccount unless configured otherwise.

### Transaction Signing
All order placement and cancellation requests are signed using the `Ed25519` standard via the `aptos-sdk`.

## 🧪 Testing

To run the integration tests for Decibel:

```bash
pytest test/hummingbot/connector/derivative/decibel_perpetual/test_decibel_perpetual_derivative.py
```

---
*Note: This connector is built using the @decibeltrade/sdk v0.3.1.*
