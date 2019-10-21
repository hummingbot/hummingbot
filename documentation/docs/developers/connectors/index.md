# Adding Exchange Connectors

## What are connectors?

Exchange connectors are modules that allow Hummingbot to connect to an exchange.  Connecting to an exchange requires constant retrieval of live exchange/order book data as well as handling interactions with the exchange.

Each exchange connector is comprised of the following components:

Component | Function
---|---
**(1) Trade execution** | Sending buy/sell/cancel instructions to the exchange.
**(2) Conforming order book data** | Formatting an exchange's order book data into the standard format used by Hummingbot.
**(3) Order book tracking** | State management: tracking exchange's real-time order book data.
**(4) Active order tracking** | State management: tracking orders placed by the bot on the exchange.
**(5) User stream tracker** | Tracking data specific to the user of the bot.

## Examples / templates

There are [existing connectors](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market) (each folder contained here is a different exchange connector) that can serve as a template for creating a new exchange connector.

Building a new exchange connector requires conforming to the template code to the new exchange's APIs, identifying and handling any differences in functions/behaviors, and testing the new exchange connector on that exchange.

- Centralized exchange: [Binance](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/binance), [Coinbase Pro](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/coinbase_pro), [Huobi](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/huobi), [Bittrex](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/bittrex)
- Ethereum DEX (0x open order book): [Radar Relay](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/radar_relay)
- Ethereum DEX (0x open order book w/coordinator support): [Bamboo Relay](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/bamboo_relay)
- Ethereum DEX (matcher model): [DDEX](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/ddex)
- Ethereum DEX (deposit/redeem model): [IDEX](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/market/idex)

## Exchange connector files

Each exchange connector consists of the following files:

```
<market_name>              # folder for specific exchange ("market")
├── *_market               # handles trade execution (buy/sell/cancel)
├── *_auth                 # handles authentication for API requests (for CEX)
├── *_data_source          # initializes and maintains a websocket connection
├── *_order_book           # takes order book data and formats it with a standard API
├── *_order_book_tracker   # maintains a copy of the market's real-time order book
├── *_active_order_tracker # for DEXes that require keeping track of
└── *_user_stream_tracker  # tracker that process data specific to the user running the bot
```

Component | Description
---|---
`*_market` | Connector modules are centered around a `Market` class, which are children of [`MarketBase`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/market_base.pyx). Each `Market` class contains a separate `OrderBookTracker` and “UserStreamTracker’ to pass along changes to the relevant order books and user accounts, respectively.<br/><br/>`Market` instances also contain a list of `InFlightOrders`, which are orders placed by Hummingbot that are currently on the order book. Typically, it is also helpful to have a market-specific `Auth` class, which generates the necessary authentication parameters to access restricted endpoints, such as for trading.
`*_auth.py` | This class handles the work of creating access requests from information provided by Hummingbot. Arguments tend to include: <ul><li>Type of request<li>Endpoint URL<li>Mandatory parameters to pass on to the exchange (e.g. API key, secret, passphrase)</ul><br/>Depending on the specific exchange, different information may be needed for authorization. Typically, the `Auth` class will:<ul><li>Generate a timestamp.<li>Generate a signature based on the time, access method, endpoint, provided parameters, and private key of the user.<li>Compile the public key, timestamp, provided parameters, and signature into a dictionary to be passed via an `http` or `ws` request.</ul><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This module is typically required for centralized exchange only.  Generally, auth for DEXs is handled by the respective `wallet`.</td></tr></tbody></table>
`*_order_book_tracker`<br/>`*_user_stream_tracker` | Each `Market` class contains an `OrderBookTracker` to maintain live data threads to exchange markets and a `UserStreamTracker` to access the current state of the user’s account and orders. Both the `OrderBookTracker` and `UserStreamTracker` have subsidiary classes which handle data access and processing.<ul><li>`OrderBookDataSource` and `UserStreamDataSource` classes contain API calls to pull data from the exchange and user accounts and WebSocket feeds to capture state changes.<li>The `OrderBook` class contains methods which convert raw snapshots from exchanges into usable dictionaries of active bids and asks.</ul>

## Placing and tracking orders

`Market` classes place orders via `execute_buy` and `execute_sell` commands, which require the following arguments:

- The order ID
- The market symbol
- The amount of the order
- The type (limit or market)
- The price, if limit order

The `execute_buy` and `execute_sell` methods verify that the trades would be legal given the trading rules pulled from the exchange and calculate applicable trading fees. They then must do the following:

- Quantize the order amount to ensure that the precision is as required by the exchange
- Create a `params` dictionary with the necessary parameters for the desired order
- Pass the `params` to an `Auth` object to generate the signature and place the order
- Pass the resulting order ID and status along with the details of the order to an `InFlightOrder`

`InFlightOrders` are stored within a list in the `Market` class, and are Hummingbot’s internal records of orders it has placed that remain open on the market. When such orders are either filled or canceled, they are removed from the list and the relevant event completion flag is passed to the strategy module.

## Exchange connector requirements
1. A complete set of exchange connector files as listed [above](#exchange-connector-files).
2. Unit tests (see [existing unit tests](https://github.com/CoinAlpha/hummingbot/tree/master/test/integration)):

    1. Exchange market test ([example](https://github.com/CoinAlpha/hummingbot/blob/master/test/integration/test_binance_market.py))
    2. Order book tracker ([example](https://github.com/CoinAlpha/hummingbot/blob/master/test/integration/test_binance_order_book_tracker.py))
    3. User stream tracker ([example](https://github.com/CoinAlpha/hummingbot/blob/master/test/integration/test_binance_user_stream_tracker.py))

3. Documentation:

    - Code commenting (particularly for any code that is materially different from the templates/examples)
    - Any specific instructions for the use of that exchange connector ([example](https://docs.hummingbot.io/connectors/binance/))

## Requirements for community-developed connectors

Introducing an exchange connector into the Hummingbot code base requires a mutual commitment from the Hummingbot team and community developers to maintaining a high standard of code quality and software reliability.

We encourage and welcome contributions from the community, subject to the guidelines and expectations outlined below.

### Guidelines for community developers
1. Provide a point of contact to the Hummingbot team.
1. Commitment to connector maintenance and keeping it up to date with Hummingbot releases. <br/>*Any connectors that are not kept up to date or have unaddressed bugs will be removed from subsequent releases of Hummingbot unless such issues are resolved.*
1. Adhere to [contributing guide](https://github.com/CoinAlpha/hummingbot/blob/master/CONTRIBUTING.md), code conventions used in the Hummingbot repo, and these guidelines outlined here.
1. Complete all of the work listed in [Exchange connector requirements](#exchange-connector-requirements).
1. Address any comments or issues raised by the Hummingbot development team during the code review process.
1. Notify the Hummingbot team and community of any known issues are bugs that are discovered.

### Expectations for the Hummingbot team
1. Make available a dedicated channel on discord (https://discord.hummingbot.io) during the initial development process.
1. Provide a main point of contact for the developer.
1. Notify developer of code changes that may affect the connector.
1. Notify the developer of any bug reports or issues reported by Hummingbot users.
1. Code review.
1. Testing and QA.

The Hummingbot team reserves the right to withhold community code contributions and excluding them from the Hummingbot code base should any such contributions fail to meet the above requirements.

## Required skills
- Python
- Prior Cython experience is a plus

## Additional resources
- [DevForum](https://forum.hummingbot.io)
- [Discord](https://discord.hummingbot.io)
- Contact the dev team: [dev@hummingbot.io](mailto:dev@hummingbot.io)