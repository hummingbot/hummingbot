# Inventory Skew

**Updated as of `v0.29.0`**

This feature lets you set and maintain a target inventory split between the base and quote assets. It prevents your overall inventory level from changing too much and may result in more stable performance in volatile markets.

## How It Works

This function adjusts the bid and ask order amounts to limit the user's trading exposure within a defined range. This prevents the user from being over-exposed from the risks of a single side of the trade when the market keeps hitting limit orders on one side only.

>**Example**: You are market making for the `BTC-USDT` pair and have 0.667 BTC and 6000 USDT. At $6000 BTC price, your total portfolio value is $10,000 and the base asset (BTC) accounts for 40% of total value. If your target base percent is 50%, your buy orders will be increased and your sell orders will be decreased until you reach the target percent.

The user specifies a target base asset percentage. Since the user's outstanding orders may change this split if they are filled, the total order size is used to define an allowable range around this target percentage. The user may expand or contract this range via a multiplier parameter.

>**Example**: You are market making for the `BTC-USDT` pair and the total value of your BTC/USDT inventory is 10 BTC. Your target base percent is 50% and each set of orders you place is 1 BTC (10% of your total portfolio). With `inventory_range_multiplier` of 1.00, your target range is 40% to 60%. With `inventory_range_multiplier` of 2.00, your target range is 30% to 70%.*

If the user's base asset value goes above the upper limit, then no bid orders would be emitted. Conversely, if the user's base asset value goes below the lower limit, then no ask orders would be emitted.

## Sample Configurations

The three bots below all share this base configuration:
```json
- market: BTC-USDT
- bid_spread: 1
- ask_spread: 1
- order_amount: 0.002
- order_levels: 3
- order_level_amount: 0.002
- order_level_spread: 1
```

### No Inventory Skew

```json
- inventory_skew_enabled: False
```
![](/assets/img/no-inventory-skew.png)

Without inventory skew, order amounts are always symmetrical between buy (outlined in green) and sell orders (outlined in red).

### Inventory Skew, Multiplier = 1
```json
- inventory_skew_enabled: True
- inventory_target_base_pct: 50
- inventory_range_multiplier: 1.0
```
![](/assets/img/skew-with-multiplier-1.png)

Since the current inventory range of each asset is within the target range (8.7% - 91.3%), both buy and sell orders are placed. However, more buy orders will be created with larger order amounts than the sell order amounts.

### Inventory Skew, Multiplier = 0.5
```json
- inventory_skew_enabled: True
- inventory_target_base_pct: 50
- inventory_range_multiplier: 0.5
```
![](/assets/img/skew-with-multiplier-0.5.png)

By decreasing the range multiplier to 0.5, the target range tightens (29.4% to 70.6%). Since the current inventory percentage (25.0% and 75%) falls off the range, only buy orders are placed until the inventory split is within range.

## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| **inventory_skew_enabled** | `Would you like to enable inventory skew? (Yes/No)` | Allows the user to set and maintain a target inventory split between base and quote assets. |
| **inventory_target_base_pct** | `On [exchange], you have [base_asset_balance] and [quote_asset_balance]. By market value, your current inventory split is [base_%_ratio] and [quote_%_ratio]. Would you like to keep this ratio?` | Target amount held of the base asset, expressed as a percentage of the total base and quote asset value. |
| **inventory_range_multiplier** | `What is your tolerable range of inventory around the target, expressed in multiples of your total order size?` | This expands the range of tolerable inventory level around your target base percent, as a multiple of your total order size. Larger values expand this range. |

## Order Size Calculation Math

The input `order_amount` in single-order mode, or its equivalent in multiple-order mode, is adjusted linearly by comparing the percentage of the base asset in the overall trading portfolio vs. the target base asset ratio.

The mathematics operations is as follows.

$o$ = order size.<br/>
$t$ = target base asset ratio.<br />
$r$ = inventory range multiplier.<br />
$s$ = total order size.<br />
$$ s = 2 \times o$$ for single order mode
$$ s = 2 \times (order\\_start\\_size \times n + {{order\\_step\\_size \times n \times (n - 1)} \over 2}) $$ for multiple order mode, with $n$ = number of orders.<br/><br/>
$b_{base}, b_{quote}$ = current balance of base and quote asset, respectively.<br />
$p$ = current price of base asset, in terms of quote asset. <br/>
$interp(x, x_0, x_1, y_0, y_1) = {y_0 + (x - x_0)({y_1 - y_0 \over x_1 - x_0})}$, i.e. the linear interpolation function.<br/>
$clamp(x, l, r) = min(max(x, l), r)$<br/><br/>
Then,<br/>

$$total\_value=b_{base} \times p + b_{quote}$$

$$base\_value=b_{base} \times p $$

$$limit_{R}, limit_{L} = (t \times total\_value) \pm r \times s \times p $$

$$bid\_adj=clamp(interp(base\_value, limit_{L}, limit_{R}, 2, 0), 0, 2)$$

$$ask\_adj=clamp(interp(base\_value, limit_{L}, limit_{R}, 0, 2), 0, 2)$$

$$bid\_size=bid\_adj \times o$$

$$ask\_size=ask\_adj \times o$$
