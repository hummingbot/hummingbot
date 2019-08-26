# Adding Exchange Connectors

!!! warning
    This document is incomplete and a work in progress.

## What are connectors?

Exchange connectors are modules that allow Hummingbot to connect to an exchange.  Each exchange connector is comprised of the following components:

Component | Function
---|---
**(1) Trade execution** | Sending buy/sell/cancel instructions to the exchange.
**(2) Conforming order book data** | Formatting an exchange's order book data into the standard format used by Hummingbot.
**(3) Order book tracking** | State management: tracking exchange's real-time order book data.
**(4) Active order tracking** | State management: tracking orders placed by the bot on the exchange.
**(5) User stream tracker** | Tracking data specific to the user of the bot.

## Examples / templates

There are [existing connectors](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market) (each folder contained here is a different exchange connector) that can serve as a template for creating a new exchange connector.

Building a new exchange connector requires conforming to the teamplate code to the new exchange's APIs, identifying and handling any differences in functions/behaviors, and testing the new exchange connector on that exchange.

- Centralized exchange: [Binance](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/binance), [Coinbase Pro](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/coinbase_pro)
- Ethereum DEX (0x open order book): [Radar Relay](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/radar_relay)
- Ethereum DEX (0x open order book w/coordinator support): [Bamboo Relay](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/bamboo_relay)
- Ethereum DEX (matcher model): [DDEX](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/ddex)
- Ethereum DEX (deposit/redeem model): [IDEX](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/idex)

## How connectors are organized

Each exchange connector consists of the following files:

```
<market_name>              # folder for specific exchange ("market")
├── *_market               # handles trade execution (buy/sell/cancel)
├── *_data_source          # initializes and maintains a websocket connection
├── *_order_book           # takes order book data and formats it with a standard API
├── *_order_book_tracker   # maintains a copy of the market's real-time order book
├── *_active_order_tracker # for DEXes that require keeping track of
└── *_user_stream_tracker  # tracker that process data specific to the user running the bot
```

## Requirements
1. A complete set of exchange connector files as listed [above](#exchange-connector-files).
2. Unit tests (see [existing unit tests](https://github.com/CoinAlpha/hummingbot/tree/master/test/integration)):

    1. Exchange market test ([example](https://github.com/CoinAlpha/hummingbot/blob/master/test/integration/test_binance_market.py))
    2. Order book tracker ([example](https://github.com/CoinAlpha/hummingbot/blob/master/test/integration/test_binance_order_book_tracker.py))
    3. User stream tracker ([example](https://github.com/CoinAlpha/hummingbot/blob/master/test/integration/test_binance_user_stream_tracker.py))

3. Documentation:

    - Code commenting (particularly for any code that is materially different from the templates/examples)
    - Any specific instructions for the use of that exchange connector ([example](https://docs.hummingbot.io/connectors/binance/))

## Required skills
- Python
- Prior Cython experience is a plus