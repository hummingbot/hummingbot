# Filled Order Delay

By default, Hummingbot places orders as soon as there are no active orders; i.e., Hummingbot immediately places a new order to replace a filled order. If there is a sustained movement in the market in any one direction for some time, there is a risk of continued trading in that direction: For example, continuing to buy and accumulate base tokens in the case of a prolonged downward move or continuing to sell in the case of a prolonged upward move.

The `filled_order_delay` parameter allows for a delay when placing a new order in the event of an order being filled, which will help mitigate the above scenarios.

>**Example**: If you have a buy order that is filled at 1:00:00 and the delay is set to `60` seconds, the next orders placed will be at 1:01:00. The sell order is also cancelled within this delay period and placed at 1:01:00 to ensure that both buy and sell orders stay in sync.

## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **filled_order_delay** | `How long do you want to wait before placing the next order if your order gets filled (in seconds)?` | How long to wait before placing the next set of orders in case at least one of your orders gets filled. |