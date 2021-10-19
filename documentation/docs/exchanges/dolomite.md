# Dolomite

[Dolomite](https://beta.dolomite.io/exchange) is a decentralized exchange powered by the Loopring Protocol that allows you to trade dozens of ERC20 token assets securely, right from your own wallet.

## Using the connector

Dolomite streamlines the decentralized exchange experience so that users can utilize the security and control of a DEX while enjoying the user interface simplicity of a centralized exchange.

An ethereum node is required in order to use Hummingbot with Dolomite. Luckily, an Ethereum node is only needed for approving tokens, which is a one-time process. So, users of the Dolomite connector can rest assured it will add virtually no extra stress to their node. See below for information on how to create an Ethereum node and wallet:

- [Creating a crypto wallet](/operation/connect-exchange/#wallets)
- [Creating an ethereum node](/operation/connect-exchange/#setup-ethereum-nodes)

In addition to the above, the user must also create an account on Dolomite. As of now, this takes 1 of 2 forms:

1. For users **inside** the US, they must create an account from the site [https://app.dolomite.io](https://app.dolomite.io).
2. For users **outside** the US, they simply must submit a trade. When Dolomite sees the first trade from a new wallet, it automatically creates an account for it.

!!! note
    The 2 criteria above holds true for where Hummingbot is running. For example, if you live outside the US, but you are running Hummingbot from within the US in the cloud (IE AWS or Azure), you still must create an account. Do reach out to us if you face any problems on doing so.

For users who have little to no prior experience using a decentralized exchange, Dolomite also has a simple account system that does not require users to setup and manage their own private keys. Read more through here in [Dolomite Traditional Accounts](https://dolomite.io/support/noncustodial-accounts).

## Miscellaneous info

### Minimum order size

The current minimum order size is $10 for takers and $40 for makers.

### Transaction fees

Dolomite has a competitive fee structure, charging 0.5% for takers and -0.1% for makers. It is the first decentralized exchange to introduce negative maker fees. Every trade that a maker places into the exchange that gets filled receives -0.1% of the value of the trade (e.g. if your maker order of $1,000 gets filled you receive a rebate of $1 in real-time).

There are no transaction fees required in order to place or cancel trades.

Some additional small flat fees may be applied to your trades. More information can be found in [this page](https://dolomite.io/support/fees).

## Contact

This connector is maintained by [Dolomite](https://beta.dolomite.io/), which can be contacted at:

- [Support Site](https://dolomite.io/support)
- [Twitter](https://twitter.com/dolomite_io?lang=en) | [Telegram](https://t.me/dolomite_official)
