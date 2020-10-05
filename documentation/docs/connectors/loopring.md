# Loopring Exchange Connector

## About Loopring

Loopring is the first scalable DEX protocol built with zkRollup for Ethereum. Loopring Exchange is the first decentralized trading platform built on top of the Loopring protocol. Loopring Exchange is accessible at Loopring.io

## Using the Connector

To use the Loopring Exchange connector to trade using Hummingbot, you will need to provide your API key, private key, and other details.

```
Enter your Loopring account id >>>
Enter the Loopring exchange id >>> 
Enter your Loopring private key >>> 
Enter your loopring api key >>> 
```

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip "Copying and pasting into Hummingbot"
    See [this page](/faq/troubleshooting/#paste-items-from-clipboard-in-putty) for more instructions in our Support section.

### Retrieving Loopring API Keys

1\. Log into your account at https://loopring.io/ using one of the supported Wallet extensions (MetaMask, MEW Wallet, WalletConnect, Authereum, Coinbase Wallet).

!!! tip
    If you have not yet created an account see [this page](https://blogs.loopring.org/loopring-exchange-faq/#how-do-i-register-an-account).

2\. Click on your account's ETH address in the top right.

3\. Click on **Export Account**.

4\. Sign the requested message that will be presented by your wallet extension of choice.

5\. You will be presented with your account information, which will include entries for "accountId", "exchangeId", "privateKey", and "apiKey". These values associated with these keys correspond to the required information you will need to connect the Loopring connector.

Make sure to keep this information private and to not share it with anyone. You can re-view this information at anytime by clicking on **Export Account** again.

!!! warning
    Please keep your EdDSA key pair and ApiKey strictly confidential. If you leak this information, your assets will be at risk. Loopring Exchange's UI and its API will never ask you for your EdDSA private key.

More information about Loopring Key Management can be found on [this page](https://docs.loopring.io/en/basics/key_mgmt.html).

## Miscellaneous Info

### Minimum Order Sizes

Minimum order sizes will vary by trading pair. Typically, the minimum total value of an order must at least 0.02 ETH equivelent.

### Transaction Fees

By default, trading fees are 0% for market makers and 0.20% for takers on Loopring. See article below for more details.

- [Fee Schedule](https://loopring.io/document/fees)

For users who are on discounted fees (VIP level 1 and above) can override the default fees used in the Hummingbot client by following our guide for [Fee Overrides](/advanced/fee-overrides/).
