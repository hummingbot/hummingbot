
### "Hanging" Orders

Typically, orders are placed as pairs e.g. 1 buy order + 1 sell order in single order mode. There is now an option using `enable_order_filled_stop_cancellation` to leave the orders on the other side hanging (not cancelled) whenever one side (buy or sell) is filled.

**Example:**

Assume you are running pure market making in single order mode, the order size is 1 and the mid price is 100. Then:

- Based on bid and ask thresholds of 0.01, your bid/ask orders would be placed at 99 and 101, respectively.
- Your current bid at 99 is fully filled, i.e. someone takes your order and you buy 1.
- By default, after the `cancel_order_wait_time`, the ask order at 101 would be cancelled.
- With the `enable_order_filled_stop_cancellation` parameter:
    - the original 101 ask order stays outstanding
    - after the `cancel_order_wait_time`, a new pair of bid and ask orders are created, resulting in a total of 1 bid order and 2 ask orders (original and new).  The original ask order stays outstanding until that is filled or manually cancelled.</ul></ul>

The `enable_order_filled_stop_cancellation` can be used if there is enough volatility such that the hanging order might eventually get filled. It should also be used with caution, as the user should monitor the bot regularly to manually cancel orders which don't get filled. It is recommended to disable inventory skew while running this feature.

| Prompt | Description |
|-----|-----|
| `Do you want to enable hanging orders? (Yes/No) >>>` | This sets `enable_order_filled_stop_cancellation` ([definition](#configuration-parameters)). |