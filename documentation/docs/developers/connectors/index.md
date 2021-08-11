# Connectors - Overview

## What are connectors?

Exchange connectors are modules that allow Hummingbot to connect to an exchange. This requires constant retrieval of live exchange/order book data and handling interactions with the exchange.

## Examples / templates

There are [existing connectors](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector). Note that each folder contained here marks different exchange connector types. These should serve as a template for creating a new exchange connector.

Building a new exchange connector requires conforming to the template code to the new exchange's APIs, identifying and handling any differences in functions/behaviors, and testing the new exchange connector on that exchange.

The following list some examples/templates that you can refer to when building the connector:

- [Crypto.com](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/crypto_com) 
- [Binance](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/binance) 
- [Coinbase Pro](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/coinbase_pro) 
- [Huobi](hhttps://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/huobi)
- [Bittrex](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/connector/exchange/bittrex)

## Exchange connector requirements

1. A complete set of exchange connector files as listed [above](https://docs.hummingbot.io/spot-connectors/overview/).
2. Unit tests (see existing unit tests [here](https://github.com/CoinAlpha/hummingbot/tree/master/test/connector) or [here](https://github.com/CoinAlpha/hummingbot/tree/master/test/integration)):
  - Exchange market test ([example](https://github.com/CoinAlpha/hummingbot/tree/master/test/connector/exchange/crypto_com/test_crypto_com_exchange.py))
  - Order book tracker ([example](https://github.com/CoinAlpha/hummingbot/tree/master/test/connector/exchange/crypto_com/test_crypto_com_order_book_tracker.py))
  - User stream tracker ([example](https://github.com/CoinAlpha/hummingbot/tree/master/test/connector/exchange/crypto_com/test_crypto_com_user_stream_tracker.py))
  - User authentication module ([example](https://github.com/CoinAlpha/hummingbot/tree/master/test/connector/exchange/crypto_com/test_crypto_com_auth.py))
3. Documentation:
  - Code commenting (particularly for any code that is materially different from the templates/examples)
  - Any specific instructions for the use of that exchange connector ([example](https://docs.hummingbot.io/spot-connectors/binance/))

3. Documentation:
  - Code commenting (particularly for any code that is materially different from the templates/examples)
  - Any specific instructions for the use of that exchange connector ([example](https://docs.hummingbot.io/connectors/binance/))

## Requirements for community-developed connectors

!!! note "Approval Required"
    If you would like to create a connector for a currently unsupported exchange, please contact the Hummingbot team to discuss beforehand and for approval. Due to the large amount of work in reviewing, testing, and maintaining exchange connectors, we will only merge in connectors that will have a meaningful benefit and impact to the Hummingbot community.

Introducing an exchange connector into the Hummingbot code base requires a mutual commitment from the Hummingbot team and community developers to maintaining a high standard of code quality and software reliability.

We encourage and welcome contributions from the community, subject to the guidelines and expectations outlined below.

### Guidelines for community developers
- Provide a point of contact to the Hummingbot team.
- Commitment to connector maintenance and keeping it up to date with Hummingbot releases. <br/>*Any connectors that are not kept up to date or have unaddressed bugs will be removed from subsequent releases of Hummingbot unless such issues are resolved.*
- Adhere to [contributing guide](https://github.com/CoinAlpha/hummingbot/blob/master/CONTRIBUTING.md), code conventions used in the Hummingbot repo, and these guidelines outlined here.
- Complete all of the work listed in [Exchange connector requirements](#exchange-connector-requirements).
- Address any comments or issues raised by the Hummingbot development team during the code review process.
- Notify the Hummingbot team and community of any known issues are bugs that are discovered.

### Acceptance
- The best way to create a connector that adheres to Hummingbot’s standard is by cloning the logic of existing connectors. We’ve done a lot of work to build our core connectors, so no need to reinvent the wheel.
- Existing connector files to use as code samples are in [Exchange connector requirements](#exchange-connector-requirements).
- While we don't require developers to have every file (You don’t need to implement a user stream if the exchange doesn’t support user stream, for instance), some general guidelines are:
    - Websocket > Rest. Hummingbot is a high-frequency trading bot, which means it’d perform better when it has all the information in real-time.
    - Adhere to conventions. Using the same naming pattern / code structure will help our developers review your code and get your connector approved faster.
    - Always add in-code comments for your custom logic.
- Required functionalities;
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
2. After the requirements above are fulfilled, we will merge the PR to `development` branch, which will be merged into `master` in the next release.
3. In the future, we may separate community-contributed connectors and strategies from the core Hummingbot codebase, so that users can choose to install exchange connectors that they are using. However, we will not do that right now.
<table><tbody><tr><td bgcolor="#ecf3ff">**General Note on Trading Pair Conversion**: </br> HummingBot's standard pair format is: `Base_Asset`-`Quote_Asset`. Therefore, a new connector that doesn't follow that convention of naming pairs would require both `convert_to_exchange_trading_pair` and `convert_from_exchange_trading_pair` methods to be implemented in the connector's market.pyx file. In addition, such connectors have to convert trading pairs in the `execute_buy` and `execute_sell` methods using the `convert_to_exchange_trading_pair` before placing order and also ensure that the dictionary keys for `self._trading_rules` are in HummingBot's pair format using `convert_from_exchange_trading_pair`. </td></tr></tbody></table>

### Expectations for the Hummingbot team
- Make available a dedicated channel on discord (https://discord.hummingbot.io) during the initial development process.
- Provide a main point of contact for the developer.
- Notify developer of code changes that may affect the connector.
- Notify the developer of any bug reports or issues reported by Hummingbot users.
- Code review.
- Testing and QA.

The Hummingbot team reserves the right to withhold community code contributions and excluding them from the Hummingbot code base should any such contributions fail to meet the above requirements.

## Required skills
- Python
- Prior Cython experience is a plus

## Additional resources
- Developer discussions, please visit the `#dev` channel on our [discord server](https://discord.hummingbot.io).
- Contact the dev team: [dev@hummingbot.io](mailto:dev@hummingbot.io)
