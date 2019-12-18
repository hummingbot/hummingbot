# IDEX Connector

## About IDEX

[IDEX](https://idex.market) is an Ethereum based decentralized smart contract exchange that allows for real-time trading. By combining aspects of centralized exchanges, it is able to enable real-time trading while maintaining blockchain settlement security protocols.

## Using the Connector

Because IDEX is a decentralized exchange, you will need an independent cryptocurrency wallet and an ethereum node in order to use Hummingbot. See below for information on how to create these:

* [Creating a crypto wallet](/installation/wallet)
* [Creating an ethereum node](/installation/node/node)

## API Key

IDEX requires an API key authentication to access API endpoints required for Hummingbot use.

```
Enter your IDEX API key >>>
```

* [Generate IDEX API key](https://docs.idex.market/#tag/API-Keys)

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

!!! tip "Copying and pasting into Hummingbot"
    See [this page](https://docs.hummingbot.io/support/how-to/#how-do-i-copy-and-paste-in-docker-toolbox-windows) for more instructions in our Get Help section.


## Miscellaneous Info

### Asset Availability for US Markets

IDEX has limit access to certain assets for customers in the US region (see [Updated Asset Availability for US Markets](https://medium.com/idex/idex-kyc-transition-period-and-updated-asset-availability-for-us-markets-set-to-begin-d45e945f842d)).

### Minimum Order Sizes

For IDEX, maker orders must be at least the equivalent of 0.15 ETH and taker orders must be at least 0.05 ETH. In general, this means that maker orders must be at minimum $40 and taker orders should be greater than $13.

### Transaction Fees

IDEX charges a 0.1% transaction fee for market makers and a 0.2% fee for market takers. In addition, market takers must pay for the gas fees of transactions, which can vary based on network traffic. For more information, check out [IDEX's FAQs](https://idex.market/faq).
