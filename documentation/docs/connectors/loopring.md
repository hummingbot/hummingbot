# Loopring

Loopring is the first scalable DEX protocol built with zkRollup for Ethereum. Loopring Exchange is the first decentralized trading platform built on top of the Loopring protocol. Loopring Exchange is accessible at Loopring.io.

## Using the connector

To use the Loopring Exchange connector to trade using Hummingbot, you will need to provide your API key, private key, and other details.

```
Enter your Loopring account id >>>
Enter the Loopring exchange address >>>
Enter your Loopring private key >>>
Enter your loopring api key >>>
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip
    For copying and pasting into Hummingbot, see [this page](https://hummingbot.zendesk.com/hc/en-us/articles/900004871203-Copy-and-paste-your-API-keys) for more instructions in our Support section.

!!! note
    Existing API keys used previously in Loopring v1 API are now invalid. Users must generate new keys from the latest version of the exchange.

### Retrieving Loopring API keys

1. Log into your account at https://loopring.io/ using one of the supported Wallet extensions (MetaMask, MEW Wallet, WalletConnect, Authereum, Coinbase Wallet).

!!! tip
    If you have not yet created an account see [this page](https://blogs.loopring.org/loopring-exchange-faq/#how-do-i-register-an-account).

2. Click on your account's ETH address in the top right.

3. Click on **Export Account**.

4. Sign the requested message that will be presented by your wallet extension of choice.

![](/assets/img/loopring-api.png)

You will be presented with your account information, which will include entries for "accountId", "exchangeAddress", "privateKey", and "apiKey". These values associated with these keys correspond to the required information to connect the Loopring connector.

Make sure to keep this information private and do not share it with anyone. However, you can review this information at any time by clicking on **Export Account** again.

!!! warning
    Please keep your EdDSA key pair and ApiKey strictly confidential. If you leak this information, your assets will be at risk. Loopring Exchange's UI and its API will never ask you for your EdDSA private key.

More information about Loopring Key Management can be found on [this page](https://docs3.loopring.io/en/basics/key_mgmt.html?h=key%20).

!!! warning
    Currently [dydx](/spot-connectors/dydx/), [terra](/protocol-connectors/terra), and [loopring](/spot-connectors/loopring/) don't work on Binary Installers. It can only be used when running Hummingbot from source or with Docker.

## Miscellaneous info

### Minimum order sizes

Minimum order sizes will vary by trading pair. Typically, the minimum total value of an order must at least 0.02 ETH equivalent.

### Transaction fees

By default, trading fees are 0% for market makers and 0.20% for takers on Loopring. See the article below for more details.

- [Fee Schedule](https://blogs.loopring.org/loopring-exchange-faq/)

For users who are on discounted fees (VIP level 1 and above) can override the default fees used in the Hummingbot client by following our guide for [Fee Overrides](/operation/override-fees).
