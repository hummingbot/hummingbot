# Price Band

**Updated as of `v0.27.0`**

This feature allows you to set a price band within which your bot places both buy and sell orders normally.

## How It Works

`price_ceiling` and `price_floor` are two optional parameters that you can set. By default, these parameters have a value of -1, which means that they are not used.

Type `config price_ceiling` and `config price_floor` to set values for these parameters. If the mid price exceeds `price_ceiling`, your bot only places sell orders. If the price falls below `price_floor`, your bot only places buy orders.

Note that the `price_floor` cannot be greater than the `price_ceiling`.

## Sample Configurations

```json
- order_refresh_time: 30
- order_refresh_tolerance_pct: 1%
- price_ceiling: 9750
- price_floor: 9730
```

With this configuration, Hummingbot will create both buy and sell orders if the mid price is between 9750 and 9730.

```
Markets:                                                                
  Exchange   Market  Best Bid Price  Best Ask Price  Mid Price          
   binance  BTCUSDT         9745.02         9746.77   9745.895          
                                                                        
Assets:                                                                 
                            BTC    USDT                                 
   Total Balance         0.0076 74.7486                                 
   Available Balance     0.0046 46.1164                                 
   Current Value (USDT) 73.8615 74.7486                                 
   Current %              49.7%   50.3%                                 
                                                                        
Orders:                                                                 
   Level  Type   Price Spread Amount (Orig)  Amount (Adj)       Age
       1  sell 9933.62  1.93%         0.003         0.003  00:00:00
       1   buy 9544.06  2.07%         0.003         0.003  00:00:00
```

Since the mid price went above `price_ceiling` of 9750, the bot only created a sell order.

```
Markets:                                                                
  Exchange   Market  Best Bid Price  Best Ask Price  Mid Price          
   binance  BTCUSDT         9754.86         9754.87   9754.865          
                                                                        
Assets:                                                                 
                            BTC    USDT                                 
   Total Balance         0.0076 74.7486                                 
   Available Balance     0.0046 46.0582                                 
   Current Value (USDT) 73.9295 74.7486                                 
   Current %              49.7%   50.3%                                 
                                                                        
Orders:                                                                 
   Level  Type   Price Spread Amount (Orig)  Amount (Adj)       Age
       1  sell  9953.8  2.04%         0.003         0.003  00:00:25
```

And when the mid price went down below the `price_floor` of 9730, Hummingbot created a buy order only.

```
Markets:                                                               
  Exchange   Market  Best Bid Price  Best Ask Price  Mid Price         
   binance  BTCUSDT         9727.17         9727.26   9727.215         
                                                                       
Assets:                                                                
                            BTC    USDT                                
   Total Balance         0.0076 74.7486                                
   Available Balance     0.0076 46.1469                                
   Current Value (USDT) 73.7199 74.7486                                
   Current %              49.7%   50.3%                                
                                                                       
Orders:                                                                
   Level Type   Price Spread Amount (Orig)  Amount (Adj)       Age
       1  buy 9533.89  1.99%         0.003         0.003  00:00:01
```


## Price Band with Order Refresh Tolerance

When it's time to refresh orders, the price band will take priority over the tolerable change in spreads.

If the mid price dips below price_floor or goes above price_ceiling, it will cancel your existing order regardless of order refresh tolerance.

```json
- order_refresh_tolerance_pct: 1%
- price_ceiling: 11750
- price_floor: 11650
```

With the above scenario, mid price dips below price floor so the bot cancel current orders regardless of the order refresh tolerance.

```
18:59:15 - (BTC-USDT) Creating 1 bid orders at (Size, Price): ['0.003 BTC, 11691.58 USDT']
18:59:16 - (BTC-USDT) Creating 1 ask orders at (Size, Price): ['0.003 BTC, 11723.73 USDT']
18:59:31 - Not cancelling active orders since difference between new order prices and current order prices is within 1.00% order_refresh_tolerance_pct
18:59:45 - Not cancelling active orders since difference between new order prices and current order prices is within 1.00% order_refresh_tolerance_pct
19:00:01 - (BTC-USDT) Cancelling the limit order buy://BTC-USDT/d81c2b6376b8b759c99c0c498d. [clock=2020-08-31 11:00:01+00:00]
19:00:01 - (BTC-USDT) Cancelling the limit order sell://BTC-USDT/e69022b440adf92952bb34e42f. [clock=2020-08-31 11:00:01+00:00]
19:00:02 - (BTC-USDT) Creating 1 ask orders at (Size, Price): ['0.003 BTC, 11725 USDT']
```

## Price Band with External Pricing Source

If `price_source` is enabled then the mid price reference point will be the external mid price.


## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **price_ceiling** | `Enter the price point above which only sell orders will be placed` | Place only sell orders when mid price goes above this price. |
| **price_floor** | `Enter the price below which only buy orders will be placed` | Place only buy orders when mid price falls below this price. |
