
### Inventory-Based Dynamic Order Sizing

[Updated as of v0.25.0]

This function adjusts the bid and ask order sizes to limit the user's trading exposure within a defined range. This prevents the user from being over-exposed from the risks of a single side of the trade when the market keeps hitting limit orders on one side only.

The user specifies a target base asset ratio and an allowable range around the target. If the user's base asset value goes above the upper limit, then no bid orders would be emitted. Conversely, if the user's base asset value goes below the lower limit, then no ask orders would be emitted.

For example, if you are targeting a 3% base asset ratio but the current value of your base asset accounts for 3.5% of the value of your inventory, then bid order amount (buy base asset) is decreased, while ask order amount (sell base asset) is increased.

| Prompt | Description |
|-----|-----|
| `Would you like to enable inventory skew? (Yes/No) >>>` | This sets `inventory_skew_enabled` ([definition](#configuration-parameters)). |
| `What is your target base asset inventory percentage? (Enter 0.01 to indicate 1%) >>>` | This sets `inventory_target_base_percent` ([definition](#configuration-parameters)). |
| `What is your tolerable range of inventory around the target, expressed in multiples of your total order size?` | This sets `inventory_range_multiplier` ([definition](#configuration-parameters)). |

**How order size is calculated**

The input `order_amount` in single-order mode, or its equivalent in multiple-order mode, is adjusted linearly by comparing the percentage of the base asset in the overall trading portfolio vs. the target base asset ratio.

The mathematics operations is as follows.

$o$ = order size.<br/>
$t$ = target base asset ratio.<br />
$r$ = inventory range multiplier.<br />
$s$ = total order size.<br />
$$ s = 2 \times o$$ for single order mode
$$ s = 2 \times (order\_start\_size \times n + {{order\_step\_size \times n \times (n - 1)} \over 2}) $$ for multiple order mode, with $n$ = number of orders.<br/><br/>
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

Here's an [inventory skew calculator](https://docs.google.com/spreadsheets/d/175AESICWSNKvU1z9Qmk_GJ2GwEn4kHdieD2wdOcQb8E/edit?usp=sharing) you can use that shows how your order sizes are adjusted.
