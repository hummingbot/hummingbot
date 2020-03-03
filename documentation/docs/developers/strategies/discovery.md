# Discovery

## Architecture

The discovery strategy is a tool for users to monitor a potentially large number of markets between two exchanges, and read the stats (e.g. bid-ask spread, potential arbitrage profits, trading volume) from matching trading symbols for discovering useful trading pairs for running market making or arbitrage strategies.

For example, a trader may use the discovery strategy to monitor the price differences between a dozen selected symbols between Binance and Bittrex for arbitrage opportunities. Once he's got Hummingbot set up monitoring the dozen symbols, he would be able to use the `status` command on Hummingbot to print out the current statistics of matching symbols between the two exchanges.

Here's a high level view of the logic flow inside the discovery strategy.

![Figure 1: Discovery strategy flow chart](/assets/img/discovery-flowchart-1.svg)

## Fetching Market Information

When initiating a discovery strategy object, the user or developer would need to specify a pair of exchanges (e.g. Binance, Huobi), a list of target assets / symbol pairs to watch (e.g. ['ETH', 'ZRX', 'ONE', 'BAT', 'ONT', 'DASH', etc.]), and optionally, a list of equivalent sets for assets that may take on different names but mean the same thing. (e.g. [["USD", "USDC", "TUSD", "PAX"]]).

When the discovery strategy is started, it would first fetch information about all the trading symbols matching the list of target assets / symbol pairs specified by the user, on both exchanges. Then, it will calculate all the possible pairings of equivalent traidng symbols on the two exchanges for calculating arbitrage profitability. e.g. if the user specified USDC and TUSD are within an equivalent set of assets, and BTC is one of the target assets specified, then "BTC-USDC" on one exchange could be matched to "BTC-TUSD" on another exchange for the purpose of calculating potential arbitrage profits.

After the market information from both exchanges have been fetched and the matching symbols have been calculated, the discovery strategy would keep using the fetched information for all ticks afterwards.

## Basic Market Stats Calculation

Assuming we've already fetched the market information from both exchanges, and the markets are ready and connected; then the discovery strategy would proceed to perform some basic market stats calculation, at every tick.

![Figure 2: Basic market stats calculation](/assets/img/discovery-flowchart-2.svg)

The strategy would calculate the basic stats for every matching trading symbol on both exchanges, and condense them into a Pandas DataFrame table for output. Each row of the table would include the trading symbol, the base asset, the quote asset, the mid, the bid-ask spread %, and 24-hr USD volume.

The basic market stats calculation logic can be found in the function `c_calculate_market_stats()` inside [discovery.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/discovery/discovery.pyx).

## Arbitrage Profitability Calculation

Besides calculating the basic stats of each trading symbol, the discovery strategy would also calculate the potential arbitrage profits between equivalent trading symbols between the two exchanges, on every tick.

![Figure 3: Arbitrage profitability calculation](/assets/img/discovery-flowchart-3.svg)

The calculation is done only for symbols that are trading equivalent assets on both exchanges. e.g. if there's a WETH-DAI pair on the left exchange, and a ETH-USDT pair on the right exchange, and ["ETH", "WETH"] and ["DAI", "USDT"] are defined as equivalent sets - then one arbitrage calculation row would be generated between WETH and ETH-USDT. On the other hand, if there's a BNB-USDT pair on the left exchange, but the right exchange doesn't trade BNB - then no arbitrage calculation would be done for BNB-USDT.

After the calculation for all matching trading pairs is done, the strategy would condense the results into a Pandas Dataframe table for output. Each row of the table would include the buy exchange name, buy symbol, sell exchange name, sell symbol, potential profit in quote asset, and potential profit in %.

The arbitrage profitability calculation logic can be found int he function `c_calculate_arbitrage_discovery()` inside [discovery.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/discovery/discovery.pyx).