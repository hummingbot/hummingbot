## Requirements

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

## API keys

When trading on a centralized exchange, you will need to connect Hummingbot and the exchange using API keys. These are account-specific credentials that allow access to live information and trading outside of the exchange website. Follow the instructions specific to your exchange on how to create API keys.

Example:

- [How to create Binance API key](https://www.binance.com/en/support/faq/360002502072)
- [How to create KuCoin API key](https://support.kucoin.plus/hc/en-us/articles/360015102174-How-to-Create-an-API)
- [How to create Coinbase Pro API key](https://help.coinbase.com/en/pro/other-topics/api/how-do-i-create-an-api-key-for-coinbase-pro)

!!! warning
      We recommend using only **read + trade** enabled API keys. It is not necessary to enable **withdraw**, **transfer**, or anything equivalent to retrieving assets from your wallet.

## Adding or replacing keys in Hummingbot

### Connect to exchanges

1. Run `connect [exchange_name]` command e.g., `connect binance` will prompt connection to Binance exchange
1. Enter API and secret keys when prompted
1. Other exchanges may require additional details such as account ID, exchange address, etc.

### Connect to Ethereum

Follow the instructions below to connect to decentralized exchanges or protocol running on Ethereum such as Balancer, Uniswap, and Perpetual Finance.

1. Run `connect ethereum` command
1. Enter your wallet private key
1. Enter the Ethereum node endpoint starting with https://
1. Enter the websocket address starting with wss://

## Checking connection status

Run the `connect` command to view the connection status. It also shows failed connections due to connectivity issues, invalid API key permissions, etc.

![](/assets/img/connection-status.png)

**Keys Added** column indicates if API keys are added to Hummingbot.

**Keys Confirmed** column shows the status if Hummingbot has successfully connected to the exchange or protocol.

**Connector Status** column is an indicator if there are known issues with the connector or working correctly. More info in [Connector Status](/connectors/#list-of-connectors/)
