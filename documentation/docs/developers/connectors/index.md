# Introduction - Connectors

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

!!! note "Approval Required"
    If you would like to create a connector for a currently unsupported exchange, please contact the Hummingbot team to discuss beforehand and for approval. Due to the large amount of work in reviewing, testing, and maintaining exchange connectors, we will only merge in connectors that will have a meaningful benefit and impact to the Hummingbot community.

Introducing an exchange connector into the Hummingbot code base requires a mutual commitment from the Hummingbot team and community developers to maintaining a high standard of code quality and software reliability.

We encourage and welcome contributions from the community, subject to the guidelines and expectations outlined below.

### Guidelines for community developers
1. Provide a point of contact to the Hummingbot team.
1. Commitment to connector maintenance and keeping it up to date with Hummingbot releases. <br/>*Any connectors that are not kept up to date or have unaddressed bugs will be removed from subsequent releases of Hummingbot unless such issues are resolved.*
1. Adhere to [contributing guide](https://github.com/CoinAlpha/hummingbot/blob/master/CONTRIBUTING.md), code conventions used in the Hummingbot repo, and these guidelines outlined here.
1. Complete all of the work listed in [Exchange connector requirements](#exchange-connector-requirements).
1. Address any comments or issues raised by the Hummingbot development team during the code review process.
1. Notify the Hummingbot team and community of any known issues are bugs that are discovered.

### Acceptance
1. The best way to create a connector that adheres to Hummingbot’s standard is by cloning the logic of existing connectors. We’ve done a lot of work to build our core connectors, so no need to reinvent the wheel.
1. Existing connector files to use as code samples are in [Exchange connector requirements](#exchange-connector-requirements).
1. While we don't require developers to have every file (You don’t need to implement a user stream if the exchange doesn’t support user stream, for instance), some general guidelines are:
    - Websocket > Rest. Hummingbot is a high-frequency trading bot, which means it’d perform better when it has all the information in real-time.
    - Adhere to conventions. Using the same naming pattern / code structure will help our developers review your code and get your connector approved faster.
    - Always add in-code comments for your custom logic.
1. Required functionalities;
    - Tracking real-time order book snapshots / diffs / trades
    - Getting prices from top of the order book
    - Order parameter quantization (Adjust any order price / quantity inputs into values accepted by the exchange, taking into account min / max order size requirement, number of digits, etc)
    - Submitting limit buy and sell orders
    - Submitting market buy and sell orders
    - Cancelling a single order
    - Cancelling all orders that the bot submitted
    - Tracking all in-flight orders
    - Updating statuses of in-flight orders
    - Updating user balance (all balance & balance available for trading)
    - Any other functionalities / error handling required in order to trade on the exchange
    - Extensive unit tests that cover all functionalities above
1. Once the PR is submitted, our developers will review your code and likely request changes. Please expect the review process to take 2-3 weeks before the PR is merged.
1. After the requirements above are fulfilled, we will merge the PR to `development` branch, which will be merged into `master` in the next release.
1. In the future, we may separate community-contributed connectors and strategies from the core Hummingbot codebase, so that users can choose to install exchange connectors that they are using. However, we will not do that right now.

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
- Developer discussions, please visit the `#dev` channel on our [discord server](https://discord.hummingbot.io).
- Contact the dev team: [dev@hummingbot.io](mailto:dev@hummingbot.io)
