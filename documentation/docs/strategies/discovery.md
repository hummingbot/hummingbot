# Discovery

## How It Works

Discovery is a meta-strategy scanning tool that helps you find profitable trading opportunities between two different exchanges. It works by taking a snapshot of the current market in coin pairs/exchanges specified by the user and calculates which are likely to provide the greatest profit. Currently it only supports the [arbitrage](/strategies/arbitrage) strategy, mixing and matching coin pair combinations across two specified exchanges to determine the best settings for which users can run bots going forward.

## Prerequisites: Inventory

Although you will not require currencies for the trading pairs on the exchanges that you choose, you will still require your API keys for centralized exchanges and a valid Ethereum Node for decentralized ones.

## Configuration Walkthrough

The following walks through all the steps when running `config` for the first time.

!!! tip "Tip: Autocomplete Inputs during Configuration"
    When going through the command line config process, pressing `<TAB>` at a prompt will display valid available inputs.

| Prompt | Description |
|-----|-----|
| `What is your market making strategy >>>` | Enter `discovery`. |
| `Import previous configs or create a new config file? (import/create) >>>` | When running the bot for the first time, enter `create`. If you have previously initialized, enter `import`, which will then ask you to specify the config file location. |
| `Enter your first exchange name >>>` | Enter an exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, `bamboo_relay`, `huobi`, `bittrex`, `dolomite`, `liquid` *(case sensitive)* |
| `Enter your second exchange name >>>` | Enter another exchange you would like to trade on.<br/><br/>Currently available options: `binance`, `radar_relay`, `coinbase_pro`, `ddex`, `idex`, `bamboo_relay`, `huobi`, `bittrex`, `dolomite`, `liquid` *(case sensitive)* |
| `Enter list of trading pairs or token names on [first exchange] >>>` | Enter the list of coin pairs that you wish to be included in Hummingbot's search for the first exchange, or hit enter to include all active pairs.<br/><br/>Pairs and tokens must be entered as an array: for example, if you want to include ZRX-WETH and WETH-DAI, you would enter it as `[ZRXWETH, WETHDAI]` or `[ZRX-WETH, WETH-DAI]` depending on the exchange. If you are interested in running discovery on all trading pairs for a single token, you may do so by entering `<$TOKEN_SYMBOL>` For instance, entering `[<ZRX>]` is the same as entering `[ZRX-USDT, ZRX-BTC, ZRX-DAI, ... ]`. |
| `Enter list of trading pairs or token names on [second exchange] >>>` | Enter the list of coin pairs that you wish to be included in Hummingbot's search for the second exchange, or hit enter to include all active pairs. Pairs and tokens must be entered as an array (see above). |
| `What is the target profitability for discovery (Default to 0.0 to list maximum profitable amounts) >>>` | Enter the minimum required profitability you would you would like Hummingbot to look for in arbitrage pairs. Pairs above the threshold will be listed when Hummingbot concludes its search, else all pairs will be listed in descending order of profitability. |
| `What is the max order size for discovery? (Default to infinity) >>>` | Enter the maximum capital that you would like Hummingbot to take advantage of arbitrage opportunities with. Hummingbot will list pairs which opportunity given your maximum capital expenditure. |


## Configuration Parameters

| Term | Definition |
|------|------------|
| **target_profitability** | The minimum required profitability that coin pair combinations must reach in order for Hummingbot to consider them a potential opportunity. |
| **target_amount** | The maximum order size that the user is willing to have Hummingbot place to take advantage of arbitrage opportunities. As this number decreases, Hummingbot will prioritize coin pair combinations with higher percentage profit than the amount of currency which can be traded at that profitability. |
