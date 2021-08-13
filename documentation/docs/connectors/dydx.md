# dYdX

dYdX describes itself as a full-featured decentralized exchange (originating from the US) for spot and margin trading. dYdX is built on Ethereum and launched at the beginning of May 2019 with spot and margin trading on ETH-DAI. dYdX claims to offer one of the most liquid order books across decentralized exchanges.

## Using the connector

Because dYdX is a decentralized exchange, you will need an independent cryptocurrency wallet and an ethereum node to use Hummingbot. See below for information on how to create these:

- [Creating a crypto wallet](/operation/connect-exchange/#wallets)
- [Creating an ethereum node](/operation/connect-exchange/#setup-ethereum-nodes)

```
Enter your Ethereum private key >>>
Which Ethereum node would you like your client to connect to? >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support section.

Also, note that your wallet must have funds deposited to dYdX to avoid getting this error when trying to connect dYdX on Hummingbot.

```
Error: DydxAPIError(status_code=400)(response={'errors': [{'name': 'AccountNotFoundError'}]})
```

!!! warning
    Currently, [dydx](/spot-connectors/dydx/) and [dydx-perpetual](/derivative-connectors/dydx-perpetual/) do not work on Binary Installers. It can only be used when running Hummingbot from source or with Docker.

## Miscellaneous info

### Minimum order sizes

Minimum order sizes will vary by trading pair. dYdX has a minimum order of 1 ETH for pairs running with ETH as the base token and 200 DAI for pairs running with DAI as base token.

### Transaction fees

By default, trading fees are 0% for market makers and 0.3% for takers on dYdX. See the article below for more details.

- [Trader Fees](https://help.dydx.exchange/en/articles/4800191-are-there-fees-to-using-dydx)
