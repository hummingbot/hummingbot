An exchange connector integrates with the API of a crypto exchange to enable high-frequency, two-way communication between the Hummingbot client and the exchange.

## Exchange types 

Hummingbot exchange connectors try to standardize trading logic and order types across many different exchanges. Connectors are designed to handle specific exchange types:

* `spot`: Connectors to central limit order book (CLOB) exchanges that trade **spot** markets
* `perp`: Connectors to central limit order book (CLOB) exchanges that trade **perpetual swap** markets
* `amm`: Connectors to automatic market maker (**AMM**) decentralized exchanges

!!! note "Centralized vs decentralized exchanges"
    Hummingbot connects to both centralized and decentralized exchanges. Centralized exchanges require users to enter API keys, while decentralized exchanges require users to connect their wallets to the underlying blockchain [protocols](/protocols).

In the future, Hummingbot aims to extend support to other exchange and asset types. Developers interested in forking Hummingbot to support other types of exchanges can discuss with the community on the **#dev** channels in the Hummingbot Discord.

## Status

Connectors may vary in quality. The CoinAlpha QA team keeps a rough indicator of each connector's working status:

* <span style="color:green; font-size:20px">⬤</span> Connector appears to be working properly.
* <span style="color:yellow; font-size:20px">⬤</span> Connector has one or more reported issues. Search for [outstanding issues](https://github.com/CoinAlpha/hummingbot/issues) related to this exchange.
* <span style="color:red; font-size:20px">⬤</span> Connector does not seem to work.

## Maintainer

Connector maintainers are responsible for fixing bugs and updating the connector when the exchange API or the Hummingbot connector spec changes.

## Adding connectors

Developers may submit connectors for review by the CoinAlpha team. Please note the [Contribution Guidelines](/developers/contributions/).

Exchanges and other institutions can visit the [official Hummingbot website](https://hummingbot.io), maintained by CoinAlpha, to discuss different ways to build and maintain connectors.

## List of connectors

### `spot`

| Exchange                                        | Website                                      | Protocol                         | Maintainer | Status                                               |
| ----------------------------------------------- | -------------------------------------------- | -------------------------------- | ---------- | ---------------------------------------------------- |
| [AscendEx](/exchanges/ascend-ex)                | [ascendex.com](https://ascendex.com/)        |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Beaxy](/exchanges/beaxy)                       | [beaxy.com](https://beaxy.com/)              |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Binance](/exchanges/binance)                   | [binance.com](https://binance.com)           |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Binance US](/exchanges/binance-us)             | [binance.us](https://www.binance.us)         |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Bitfinex](/exchanges/bitfinex)                 | [bitfinex.com](https://bitfinex.com)         |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [BitMart](/exchanges/bitmart)                   | [bitmart.com](https://www.bitmart.com/)      |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [Bittrex Global](/exchanges/bittrex)            | [bittrex.com](https://bittrex.com)           |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [Blocktane](/exchanges/blocktane)               | [blocktane.io](https://blocktane.io/)        |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [Coinbase Pro](/exchanges/coinbase)             | [pro.coinbase.com](https://pro.coinbase.com) |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [Coinzoom](/exchanges/coinzoom)                 | [coinzoom.com](https://www.coinzoom.com/)    |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [Crypto.com](/exchanges/crypto-com)             | [crypto.com](https://crypto.com)             |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Digifinex](/exchanges/digifinex)               | [digifinex.com](https://www.digifinex.com/)  |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [FTX](/exchanges/ftx)                           | [ftx.com](https://ftx.com/foundation)        |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Gate.io](/exchanges/gate-io)                   | [gate.io](https://www.gate.io/)              |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [HitBTC](/exchanges/hitbtc)                     | [hitbtc.com](https://hitbtc.com/)            |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Huobi Global](/exchanges/huobi)                | [huobi.com](https://huobi.com)               |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Kraken](/exchanges/kraken)                     | [kraken.com](https://kraken.com)             |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [KuCoin](/exchanges/kucoin)                     | [kucoin.com](https://kucoin.com)             |                                  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Liquid](/exchanges/liquid)                     | [liquid.com](https://liquid.com)             |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [NDAX](/exchanges/ndax)                         | [ndax.io](https://ndax.io/)                  |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [OKEx](/exchanges/okex)                         | [okex.com](https://www.okex.com/)            |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [ProBit Global](/exchanges/probit)              | [probit.com](https://www.probit.com/)        |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [ProBit Korea](/exchanges/probit-korea/)        | [probit.kr](https://www.probit.kr/en-us/)    |                                  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [dYdX](/exchanges/dydx)                         | [dydx.exchange](https://dydx.exchange/)      | [ethereum](/protocols/ethereum)  | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Loopring](/exchanges/loopring)                 | [loopring.org](https://loopring.org)         | [ethereum](/protocols/ethereum)  | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |

### `perp`

| Exchange                                         | Website                                      | Protocol                          | Maintainer | Status                                               |
| ------------------------------------------------ | -------------------------------------------- | --------------------------------- | -----------| ---------------------------------------------------- |
| [Binance Futures](/exchanges/binance-perpetual)  | [binance.com](https://binance.com)           |                                   | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Bybit](/exchanges/bybit-perpetual)               | [bybit.com](https://www.bybit.com/en-US/)   |                                   | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [dYdX Perpetual](/exchanges/dydx-perpetual)      | [dydx.exchange](https://dydx.exchange/)      | [ethereum](/protocols/ethereum)   | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |

### `amm`

| Exchange                                         | Website                                      | Protocol                          | Maintainer | Status                                               |
| ------------------------------------------------ | -------------------------------------------- | --------------------------------- | ---------- | ---------------------------------------------------- |
| [Balancer](/exchanges/balancer)                  | [balancer.fi](https://balancer.fi/)          | [ethereum](/protocols/ethereum)   | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Celo](/protocols/celo)                         | [celo.org](https://celo.org/)                | [celo](/protocols/celo)           | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [Perpetual Finance](/exchanges/perp-fi/)         | [perp.exchange](https://perp.exchange/)      | xdai                              | CoinAlpha  | <span style="color:red; font-size:25px">⬤</span> |
| [Terra](/exchanges/terra/)                       | [terra.money](https://www.terra.money/)      | [terra](/protocols/terra)         | CoinAlpha  | <span style="color:green; font-size:25px">⬤</span> |
| [Uniswap](/exchanges/uniswap/)                   | [uniswap.org](https://uniswap.org/)          | [ethereum](/protocols/ethereum)   | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |
| [Uniswap v3](/exchanges/uniswap-v3)              | [uniswap.org](https://uniswap.org/)          | [ethereum](/protocols/ethereum)   | CoinAlpha  | <span style="color:yellow; font-size:25px">⬤</span> |


