# dYdX Perpetual

dYdX is a leading decentralized exchange that currently supports perpetual, margin trading, spot trading, lending, and borrowing. dYdX runs on smart contracts on the Ethereum blockchain, and allows users to trade with no intermediaries.

## Prerequisites

### Supported installation types

Currently, this connector does not work on binary installation. Install Hummingbot via Docker or from source to use this connector.

- Install via Docker: [Linux](/installation/linux/#install-via-docker) | [Windows](/installation/windows/#install-via-docker) | [macOS](/installation/mac/#install-via-docker) | [Raspberry Pi](/installation/raspberry/)
- Install from source: [Linux](/installation/linux/#install-from-source) | [Windows](/installation/windows/#install-from-source) | [macOS](/installation/mac/#install-from-source) | [Raspberry Pi](/installation/raspberry/#install-from-source)

### API credentials and stark key

1. Connect your Ethereum wallet to dydx Perpetual
   - [How to deposit USDC or any ERC-20 token into your L2 Perpetual account](https://help.dydx.exchange/en/articles/5108497-how-to-deposit-usdc-or-any-erc-20-token-into-your-l2-perpetual-account?utm_content=article_5108497)
2. You need the following to connect Hummingbot to the exchange:
   - API key. [Connect to Exchange Guide](/operation/connect-exchange).
   - API secret key
   - Passphrase
   - Account number (Always set value to **0** for now)
   - Stark private key

API credentials and a stark private key can be obtained programmatically using their documentation:

- [Recover Default API Credentials](https://docs.dydx.exchange/?python#recover-default-api-credentials)
- [Derive StarkKey](https://docs.dydx.exchange/?python#derive-starkkey)

Alternatively, you can follow these steps to get the required credentials:

1. From the dydx Perpetuals exchange, right-click anywhere on your web browser, and select **Inspect** to open Developer Tools
2. Go to Application > Local Storage > https://trade.dydx.exchange
3. Select **STARK_KEY_PAIRS** and click the drop-down next to your wallet address to get the stark private key
4. Select **API_KEY_PAIRS** and click the drop-down next to your wallet address to get the API key, secret key, and passphrase

### Ethereum wallet address

You can use any Ethereum wallet address to connect to Hummingbot. If you're new to this and unsure which one to use, most of our users are on MetaMask.

- [MetaMask - Getting Started](https://metamask.io/faqs.html)

## Connecting to exchange

1. From Hummingbot, run `connect dydx_perpetual` command
2. Enter the required dydx Perpetual credentials on each prompt
3. Enter your Ethereum wallet address
4. Hummingbot will confirm when you have successfully connected to the exchange

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support section.

## Minimum order sizes

Their help article below provides information on the minimum order size per asset.

- [Minimum Trade Sizes](https://help.dydx.exchange/en/articles/4798055-what-is-the-minimum-order-size-on-perpetuals)

## Transaction fees

By default, trading fees are 0.05% for market makers and 0.20% for takers on dYdX. See the article below for more details.

- [Perpetual Trade Fees](https://help.dydx.exchange/en/articles/4798040-perpetual-trade-fees)
