# Minimum Spread

**Released on version [0.28.0](/release-notes/0.28.0)**

This parameter allows Hummingbot to cancel the active order right away when its spread dips below the specified value.

## `minimum_spread`

If the spread of any active order falls below this param value, it will be automatically canceled.

** Prompt: **

```json
At what minimum spread should the bot automatically cancel orders?
>>>
```

## How it works

The strategy checks the active order's spread on every tick (1 second).

By default, this is set to `-100`. Setting this parameter to a negative value disables this feature. To enable, run the `config minimum_spread` command in the Hummingbot client and specify your minimum spread value.

This only applies to active orders and does not affect hanging orders.

## Sample configuration

```json
- bid_spread : 0.50
- ask_spread : 0.50
- minimum_spread : 0.49
- order_refresh_time : 60.0
```

With the above configuration, the bot creates buy and sell orders at 0.5% spread from mid-price.

```
00:28:31 - Creating 1 bid orders at (Size, Price): ['0.05 ETH, 227.41USDC']
00:28:31 - Creating 1 ask orders at (Size, Price): ['0.05 ETH, 229.69USDC']
00:28:31 - Created LIMIT_MAKER BUY order x-XEKWYICX-BEHUC1593217711001924 for 0.05000000 ETHUSDC.
00:28:31 - Created LIMIT_MAKER SELL order x-XEKWYICX-SEHUC1593217711002203 for 0.05000000 ETHUSDC.
```

```
Orders:
   Level  Type  Price Spread Amount (Orig)  Amount (Adj)       Age
       1  sell 229.69  0.49%          0.05          0.05  00:00:00
       1   buy 227.41  0.50%          0.05          0.05  00:00:00
```

Even before the 60 seconds refresh time was up, the sell order was canceled when its spread went below the minimum.

```
00:28:40 - Order is below minimum spread (0.0049). Cancelling Order: (Sell) ID - x-XEKWYICX-SEHUC1593217711002203
00:28:40 - Cancelling the limit order x-XEKWYICX-SEHUC1593217711002203.
```

```
Orders:
   Level Type  Price Spread Amount (Orig)  Amount (Adj)       Age
       1  buy 227.41  0.52%          0.05          0.05  00:00:12
```

In the next order refresh, new buy and sell orders with 0.5% spreads will be created.
