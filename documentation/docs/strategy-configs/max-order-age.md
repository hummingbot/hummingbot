# Max Order Age

**Released on version [0.34.0](/release-notes/0.34.0)**

## How it works

By default, the parameter is set to 1800 seconds.

To reconfigure, run the command `config max_order_age` and set the desired value in seconds.

The `max_order_age` parameter allows you to set a specific duration when resetting your order's age. It refreshes your orders and automatically creates an order based on the spread and movement of the market. Also, hanging orders remain as hanging orders.

![](/assets/img/config.gif)

## Sample configuration

We can set the maximum age of an order before it refreshes back to the set spread and amount. The example below shows that it refreshed the order's age before `order_refresh_time` was triggered because `max_order_age` was set to 20 seconds.

```json
bid_spread : 0.50
ask_spread : 0.50
max_order_age : 20.0
order_refresh_time : 60.0
```

![](/assets/img/max-order-age.png)

### Max order age with order refresh tolerance

Setting our `max_order_age` at a lower time than `order_refresh_time` refreshes our orders based on the last spread and value.

Now try out a configuration without max order age, and let's enable order refresh tolerance.

```json
bid_spread : 0.50
ask_spread : 0.50
order_refresh_tolerance_pct: 0.1
order_refresh_time : 60.0
```

![](/assets/img/order-refresh-tolerance.png)

The orders are not canceling because it is within the 0.1% order refresh tolerance percentage even though the order refresh time is 30 seconds.

Now add max order age to the config.

```json
bid_spread : 0.50
ask_spread : 0.50
order_refresh_tolerance_pct: 0.02
max_order_age: 15.0
order_refresh_time : 30.0
```

![](/assets/img/different-config.png)

The `max_order_age` parameter tried to refresh the order but `order_refresh_tolerance_pct` kicked in. That's why the order was canceled, and the bot created a new order because it reached the threshold of 0.02%.

![](/assets/img/different-config2.png)

### Max order age with hanging orders

Max order age respects hanging orders and refreshes the orders but does not cancel active hanging orders. See the example below.

```json
ask_spread: 0.3
bid_spread: 0.3
order_refresh_time: 60
max_order_age: 30
hanging_order_enabled: True
```

![](/assets/img/max_order_hanging_order.gif)

The hanging orders were not canceled and were only refreshed when `max_order_age` was triggered.

### Why max order age is important in liquidity mining?

Suppose you are participating in the `HARD-USDT` campaign with an order refresh time of 30 minutes. Max order age refreshes depending on what you set it on as long as it is lower than the order refresh time. When participating in liquidity mining, outstanding orders that reach the 30-minute mark are not subject to rewards. Therefore, it is best to use the parameter to refresh the orders' age to be eligible for rewards.
