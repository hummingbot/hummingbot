# Discovery

## Architecture

The discovery strategy is a tool for users to monitor a potentially large number of markets between two exchanges, and read the stats (e.g. bid-ask spread, potential arbitrage profits, trading volume) from matching trading symbols for discovering useful trading pairs for running market making or arbitrage strategies.

For example, a trader may use the discovery strategy to monitor the price differences between a dozen selected symbols between Binance and IDEX for arbitrage opportunities. Once he's got Hummingbot set up monitoring the dozen symbols, he would be able to use the `status` command on Hummingbot to print out the current statistics of matching symbols between the two exchanges.

Here's a high level view of the logic flow inside the discovery strategy.

![Figure 1: Discovery strategy flow chart](/assets/img/discovery-flowchart-1.svg)

## Fetching Market Information



## Basic Market Stats Calculation

## Arbitrage Profitability Calculation