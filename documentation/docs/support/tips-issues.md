# Tips & Known Issues

## Edit the configuration files directly

You may find it easier to edit the configuration files rather than using Hummingbot's `config` command. The [configuration files](/configuration/#sample-config-files) are automatically created after the first time the user runs the `config` command.

## Use your Metamask Ethereum address

If you use the same Ethereum address for both Hummingbot and [Metamask](https://metamask.io), you can  navigate to a decentralized exchange's website and observe the orders created and trades filled by Hummingbot.

## Trading pair syntax differences

Hummingbot throws an error if the trading pair entered by the user isn't available on the exchange. However, each exchange may have different syntax for their trading pairs, and different trading pairs, by convention, may switch the base asset and the quote asset.

Below are some trading pairs and their equivalents on different exchanges:

* DDEX: `BAT-WETH`, `ZRX-WETH`, `WETH-DAI`
* Binance: `BATETH`, `ZRXETH`, `ETHUSDT`

!!! tip
    Symbols differ across exchanges for technical reasons, not just arbitrary exchange nomenclature preferences.  For example, ETH and BTC on a centralized exchange would correspond to WETH and WBTC on a decentralized exchange, with the "wrapped" versions of ETH and BTC existing to enable interoperability with the DEX.

## Delay on initial startup due to DEX ERC-20 token approval

When first starting Hummingbot, it may initially take several minutes before Hummingbot will begin placing orders.  This is because Hummingbot will call the `Approve()` function on the the ERC-20 tokens to be traded on the DEX, which is an instruction that is sent to the Ethereum blockchain that will need to be mined.

Read more about this here: [ERC-20 tokens](https://en.wikipedia.org/wiki/ERC-20) or [ERC20 Approve/Allow Explained](https://medium.com/ethex-market/erc20-approve-allow-explained-88d6de921ce9).

## Time synchronization needs to be enabled

Certain exchange APIs may not function correctly and will throw errors if the user's operating system clock differs from the exchange's server clock by more than a few seconds. Time sync is enabled by default in OS X and Linux, but users who overrode the system defaults need to activate it in order to use Hummingbot.
