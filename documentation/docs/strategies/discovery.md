# Discovery

## How it Works

Discovery is a meta-strategy scanning tool that helps you find profitable trading opportunities between two different exchanges. It works by taking a snapshot of the current market in coin pairs/exchanges specified by the user and calculates which are likely to provide the greatest profit. Currently it only supports the [arbitrage](/strategies/arbitrage) strategy, mixing and matching coin pair combinations across two specified exchanges to determine the best settings for which users can run bots going forward.

## Prerequisites: Inventory

Although you will not require currencies for the trading pairs on the exchanges that you choose, you will still require your API keys for centralized exchanges and a valid Ethereum Node for decentralized ones.

## Configuration Walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>`: | Enter `discovery`.<br/><br/>Currently available options: `arbitrage` or `cross_exchange_market_making` or `pure_market_making` or `discovery` or `simple_trade` *(case sensitive)* |
| `Import previous configs or create a new config file? (import/create) >>>`: | When running the bot for the first time, enter `create`.<br/>If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your first exchange name >>>`: | Enter an exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, `bamboo_relay`, `huobi`, `bittrex` *(case sensitive)* |
| `Enter your second exchange name >>>`: | Enter another exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, `bamboo_relay`, `huobi`, `bittrex` *(case sensitive)* |
| `Enter list of trading pairs or token names on $FIRST_EXCHANGE >>>` | Enter the list of coin pairs that you wish to be included in Hummingbot's search for the first exchange, or hit enter to include all active pairs.<br/><br/>Pairs and tokens must be entered as an array: for example, if you want to include ZRX-WETH and WETH-DAI, you would enter it as `[ZRXWETH, WETHDAI]` or `[ZRX-WETH, WETH-DAI]` depending on the exchange. If you are interested in running discovery on all trading pairs for a single token, you may do so by entering `<$TOKEN_SYMBOL>` For instance, entering `[<ZRX>]` is the same as entering `[ZRX-USDT, ZRX-BTC, ZRX-DAI, ...]`. |
| `Enter list of trading pairs or token names on $SECOND_EXCHANGE >>>` | Enter the list of coin pairs that you wish to be included in Hummingbot's search for the second exchange, or hit enter to include all active pairs. Pairs and tokens must be entered as an array (see above). |
| `What is the target profitability for discovery (default to 0.0 to list maximum profitable amounts) >>>`: | Enter the minimum required profitability you would you would like Hummingbot to look for in arbitrage pairs. Pairs above the threshold will be listed when Hummingbot concludes its search, else all pairs will be listed in descending order of profitability. |
| `What is the max order size for discovery? (default to infinity) >>>` | Enter the maximum capital that you would like Hummingbot to take advantage of arbitrage opportunities with. Hummingbot will list pairs which opportunity given your maximum capital expenditure. |
| `Would you like to import an existing wallet or create a new wallet? (import / create) >>>`: | Import or create an Ethereum wallet which will be used for trading on DDEX.<br/><br/>Enter a valid input:<ol><li>`import`: imports a wallet from an input private key.</li><ul><li>If you select import, you will then be asked to enter your private key as well as a password to lock/unlock that wallet for use with Hummingbot</li><li>`Your wallet private key >>>`</li><li>`A password to protect your wallet key >>>`</li></ul><li>`create`: creates a new wallet with new private key.</li><ul><li>If you select create, you will only be asked for a password to protect your newly created wallet</li><li>`A password to protect your wallet key >>>`</li></ul></ol><br/><table><tbody><tr><td bgcolor="#e5f8f6">**Tip**: using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.</td></tr></tbody></table> |
| `Which Ethereum node would you like your client to connect to? >>>`: | Enter an Ethereum node URL for Hummingbot to use when it trades on Ethereum-based decentralized exchanges.<br /><br />For more information, see: Setting up your Ethereum Node](/installation/node/node).<table><tbody><tr><td bgcolor="#ecf3ff">**Tip**: if you are using an Infura endpoint, ensure that you append `https://` before the URL.</td></tr></tbody></table> |

## Configuration Parameters

| Term | Definition |
|------|------------|
| **target_profitability** | The minimum required profitability that coin pair combinations must reach in order for Hummingbot to consider them a potential opportunity. |
| **target_amount** | The maximum order size that the user is willing to have Hummingbot place to take advantage of arbitrage opportunities. As this number decreases, Hummingbot will prioritize coin pair combinations with higher percentage profit than the amount of currency which can be traded at that profitability. |
