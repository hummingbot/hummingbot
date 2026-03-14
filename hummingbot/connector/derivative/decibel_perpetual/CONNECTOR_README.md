# Decibel Perpetual Connector

## Overview

This connector integrates [Decibel](https://decibel.fi/) — a decentralized perpetual futures exchange built on the [Aptos](https://aptosfoundation.org/) blockchain — into Hummingbot.

Key characteristics:
- **Decentralized**: All order placement and cancellation happen as on-chain Aptos transactions, NOT via REST API.
- **REST API**: Used only for market data, account information, and order status polling.
- **Authentication**: Bearer token from [geomi.dev](https://geomi.dev) for REST API; Ed25519 private key for signing on-chain transactions.
- **Collateral**: USDC only.
- **Position mode**: ONEWAY (net positions) only.
- **Fees**: Maker 0.015%, Taker 0.04% (fixed).

---

## Requirements

| Item | Details |
|---|---|
| API Key | Bearer token from [geomi.dev](https://geomi.dev) |
| API Wallet | Aptos wallet (public + private key) — used to sign on-chain transactions |
| Main Wallet | Aptos wallet address — used for account/balance lookups |
| Python package | `aptos-sdk` (recommended) or `cryptography` (fallback) |

Install the Aptos SDK:
```bash
pip install aptos-sdk
```

---

## Configuration

When you run `connect decibel_perpetual` in Hummingbot, you will be prompted for:

| Field | Description |
|---|---|
| `decibel_perpetual_api_wallet_public_key` | Aptos address of the API wallet that signs transactions |
| `decibel_perpetual_api_wallet_private_key` | Ed25519 private key (hex) of the API wallet |
| `decibel_perpetual_main_wallet_public_key` | Aptos address of your main trading account |
| `decibel_perpetual_api_key` | Bearer token from geomi.dev for REST API access |

---

## Architecture

```
DecibelPerpetualDerivative (connector core)
├── DecibelPerpetualAuth          ← Bearer token for REST; private key for txns
├── DecibelPerpetualWebUtils      ← REST URL helpers, WebAssistantsFactory
├── DecibelPerpetualAPIOrderBookDataSource  ← REST-polled order book, trades, funding
├── DecibelPerpetualUserStreamDataSource    ← REST-polled balances, positions, orders
└── DecibelPerpetualTransactionBuilder     ← Aptos on-chain order placement/cancel
```

### Order Flow

1. Hummingbot calls `_place_order()`.
2. Connector converts price/size to chain units (using `px_decimals`/`sz_decimals` from market info).
3. `DecibelPerpetualTransactionBuilder` builds an Aptos `EntryFunction` transaction for `market::place_order`.
4. Transaction is signed with the API wallet Ed25519 key.
5. Transaction is submitted to the Aptos fullnode REST API.
6. The transaction hash is used as the exchange order ID.

### Order Cancellation Flow

1. Hummingbot calls `_place_cancel()`.
2. `DecibelPerpetualTransactionBuilder` builds an Aptos `EntryFunction` transaction for `market::cancel_order`.
3. Transaction is signed and submitted; returns on success.

---

## Supported Markets

All markets available on Decibel (e.g. `BTC-USD`, `ETH-USD`, `SOL-USD`). Fetch the list with:

```
GET https://api.mainnet.aptoslabs.com/decibel/api/v1/markets
Authorization: Bearer <your_api_key>
```

---

## Supported Order Types

| Hummingbot Order Type | Decibel Equivalent |
|---|---|
| `LIMIT` | Limit order (GTC) |
| `LIMIT_MAKER` | Post-only limit order |

Market orders are NOT directly supported. They are approximated using IOC limit orders with configurable slippage (default 8%).

---

## Testnet

Use `connect decibel_perpetual_testnet` to connect to the Aptos testnet deployment.

Base URL: `https://api.testnet.aptoslabs.com/decibel`

---

## References

- Decibel: https://decibel.fi/
- Aptos: https://aptosfoundation.org/
- Geomi (API key provider): https://geomi.dev/
- Aptos Python SDK: https://github.com/aptos-labs/aptos-python-sdk
- Hummingbot GitHub issue: https://github.com/hummingbot/hummingbot/issues/8028
