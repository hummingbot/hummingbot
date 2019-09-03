# Arbitrage

## Architecture

The strategy constantly scans for any arbitrage opportunity by comparing the order books on two markets that are trading equivalent assets (e.g. WETH-USDC vs. ETH-USD). Whenever it finds any price dislocation between the two markets (i.e. it's profitable to buy from one and sell to the other), it would calculate the optimal order size to do the arbitrage trade, and trades away the price difference by sending opposing market orders to both markets.

Here's a high level view of the logic flow inside the built-in arbitrage strategy.

![Figure 1: Arbitrage strategy flow chart](/assets/img/arbitrage-flowchart-1.svg)

There are a few major parts to the arbitrage strategy in terms of its logic flow:

 1. Sanity checks, before scanning for arbitrage opportunities
 2. Scanning for profitable arbitrage trades
 3. Calculating the optimal arbitrage size
 4. Executing the arbitrage orders

## Sanity Checks

Before the strategy looks at the two markets for profitable trades, it needs to check whether it is safe to do any trades first.

There are a few conditions that the strategy would check for at every tick, before proceeding to looking at the market order books:

 1. Are both markets connected and ready?
 
    If any of the left or right markets is not ready, or is disconnected; then no arbitrage trade is possible.
 
 2. Are there pending market orders on the markets that are still being processed?

    If there are outstanding market orders still being processed in the markets, then no further arbitrage trade is possible.
 
 3. Has there been a recent arbitrage trade within the cooldown period?

    If an arbitrage trade has happened recently, within the cooldown period (the `next_trade_delay_interval` init argument in [arbitrage.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/arbitrage/arbitrage.pyx)), then no arbitrage is possible for this tick. This wait is needed because asset balances on markets often need some delay before they are updated, after the last trade.

## Scanning For Profitable Arbitrage Trades

After the sanity checks have passed, the strategy would look at the top of the two markets' order books to see if any profitable arbitrage is possible. This is only possible if one of the following happens:

 1. The price of the bid order book on the left market is higher than the price of the ask order book on the right market; or
 2. The price of the bid order book on the right market is higher than the price of the ask order book on the left market.

In either case, the arbitrage strategy would be able to sell into the higher bid book and buy from the lower ask book. If none of the above is true at the current tick, then the arbitrage strategy would wait for the next tick and repeat the same process.

The profitable arbitrage check logic can be found in the function `c_calculate_arbitrage_top_order_profitability()` inside [arbitrage.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/arbitrage/arbitrage.pyx).

## Calculating the Optimal Arbitrage Size

After an arbitrage opportunity is found, the next step is to calculate the optimal order size for the arbitrage trade.

![Figure 2: Calculating the optimal arbitrage size](/assets/img/arbitrage-flowchart-2.svg)

Arbitrage opportunities are always limited in size - as you buy higher and higher into the ask book and sell lower and lower into the bid book, the amount of profit decreases for every increment of order size. Eventually, the price you buy and sell into the two books would become the same and you would no longer make more money by increasing the order size further. So the arbitrage strategy would calculate the maximum order size you can make by examining the order books on the two markets.

Another thing the arbitrage strategy takes into account is the transaction fee of the markets. Some markets has a fixed or semi-fixed fee for every trade, s.t. you'd need a certain minimum order size for the arbitrage before it would make any profit. The arbitrage strategy would try to take that into account and calculate the correct order size that produces the most profits.

Finally, the arbitrage strategy will look at the balance of assets availble for trading in both the left and right markets - the arbitrage order size cannot exceed the amount of assets that can be traded.

The optimal arbitrage size calculation logic can be found in the functions `c_find_best_profitable_amount()` and `c_find_profitable_arbitrage_orders()` inside [arbitrage.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/arbitrage/arbitrage.pyx).

## Executing the Arbitrage Orders

If the calculated arbitrage size is greater than 0, then the arbitrage strategy would send both the market buy and market sell orders to the two markets simultaneously. Arbitrage opportunities are usually rare and are quickly exploited by traders, and so it is important to send both orders out without any wait.

The order execution logic can be found in the function `c_process_market_pair_inner()` inside [arbitrage.pyx](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/arbitrage/arbitrage.pyx).