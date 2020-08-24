# Hummingbot market making tips

- Experiment with different combinations of order spread and size.
- Use [paper trading](https://docs.hummingbot.io/operation/paper-trade/) to experiment with various strategy configurations before risking real capital.
- Set wider spreads. Unless you are Binance VIP 9+, you are at a disadvantage compared to other market makers at lower spreads because of trading fees. Starting closer to the max spread per side in each market (see [Active Programs](https://docs.hummingbot.io/liquidity-mining/#active-programs)).
- Another way to look at it is that your bot shouldn't be trading all the time. If you're constantly filling orders, it's a sign that your spreads might be too tight. It is suggested to watch the order book on Binance while your bot is running and counting how much volume is ahead of you in the order book.
- Set `order_levels` to more than 1. This allows you to tailor how your orders are configured. For example, you can have a smaller amount at 0.5% spread and a larger amount at 0.9% spread.
- Use the Inventory Skew feature - this keeps your inventory position more stable over time.
- For users using **multiple orders + inventory skew**, we found that reducing the `inventory_range_multiplier` below 1.00 helps to dampen volatility. Because the total order size is used to set a band around the target percentage, using multiple orders inflates that band. Reducing `inventory_range_multiplier` to below 1 will narrow the band (Target base asset range in the status output).

    ![Inventory Range Multiplier](/assets/img/inventory_range_multiplier.png)

- Increase the `filled_order_delay` parameter to 60 seconds or more. This prevents your bot from buying or selling a lot when the market is steeply trending in one direction.

# General market making tips

- Picking which market to trade on is important. For example, ETH/BTC is a very active pair dominated by sophisticated professional market makers. Consider picking markets with less competition, either on smaller exchanges or less active pairs.
- The opportunity for market makers can be calculated as spread * volume. you can use sites like [CoinGecko](https://www.coingecko.com/en) like get these metrics for all pairs in the market.
- Without additional compensation, it's not easy to make money by market making. That's why we are working with projects and exchanges to let them put up reward pools for market makers through liquidity mining campaign.