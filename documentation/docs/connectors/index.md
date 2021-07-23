# Connectors

## What are Connectors?

Connectors are packages of code that link Hummingbot's internal trading algorithms with live information from different cryptocurrency exchanges. They interact with a given exchange's API, such as by gathering order book data and sending and cancelling trades. See below for the list of exchanges which Hummingbot currently has connectors to.

Related article : [How connectors are integrated into Hummingbot](https://hummingbot.zendesk.com/hc/en-us/articles/900004506986)

## Exchange Types

### Spot

Spot connectors connect to order book exchanges that trade spot markets.

### Perpetual

These connectors connect to order book exchanges that trade perpetual swap markets.

### AMM

Protocol connectors connect to automatic market maker (AMM) exchanges on various blockchain protocols.

### Decentralized (DEX)

DEX connectors connect to decentralized exchanges that operate on Layer 1 or Layer 2 blockchains.


| Exchange                                    | Type        | DEX       | Website                                      | Status                                              | Notes                                |
----------------------------------------------|-------------|-----------|----------------------------------------------| --------------------------------------------------- | -------------------------------------|
| [Binance](/connectors/binance)              | spot        | N/A       | [binance.com](https://binance.com)           | <span style="color:green; font-size:25px">⬤</span> | |
| [Bittrex Global](/connectors/bittrex)       | spot        | N/A       | [bittrex.com](https://bittrex.com)           | <span style="color:green; font-size:25px">⬤</span> | |
| [Bitfinex](/connectors/bitfinex)            | spot        | N/A       | [bitfinex.com](https://bitfinex.com)         | <span style="color:green; font-size:25px">⬤</span> | |
| [Coinbase Pro](/connectors/coinbase)        | spot        | N/A       | [pro.coinbase.com](https://pro.coinbase.com) | <span style="color:green; font-size:25px">⬤</span> | |
| [Crypto.com](/connectors/crypto-com)        | spot        | N/A       | [crypto.com](https://crypto.com)             | <span style="color:green; font-size:25px">⬤</span> | |
| [Huobi Global](/connectors/huobi)           | spot        | N/A       | [huobi.com](https://huobi.com)               | <span style="color:green; font-size:25px">⬤</span> | |
| [Kraken](/connectors/kraken)                | spot        | N/A       | [kraken.com](https://kraken.com)             | <span style="color:green; font-size:25px">⬤</span> | |
| [KuCoin](/connectors/kucoin)                | spot        | N/A       | [kucoin.com](https://kucoin.com)             | <span style="color:green; font-size:25px">⬤</span> | |
| [Liquid](/connectors/liquid)                | spot        | N/A       | [liquid.com](https://liquid.com)             | <span style="color:green; font-size:25px">⬤</span> | |
| [Loopring](/connectors/loopring)            | spot        | ethereum  | [loopring.org](https://loopring.org)         | <span style="color:green; font-size:25px">⬤</span> | |
