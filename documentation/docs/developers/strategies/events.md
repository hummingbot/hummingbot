# Events

## What is an event

**Events** are a key part of how strategies are executed.

They are classes that can be used inside the strategy code that defines code must be executed when the respective event happens.

All the possible events are inside the [events.py](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/event/events.py) file.

## Calling an event inside a strategy

(Add description and example of how events are used inside the strategy)

## Existing events

### Market Order Failure

(Below is a simple example. Add all the existing events that exist on the code)

The class `MarketOrderFailureEvent(NamedTuple)` is executed when there is an error when sending an order to the connector

Example:
```python
from hummingbot.core.event.events import MarketOrderFailureEvent

    def did_fail_order(self, order_failed_event: MarketOrderFailureEvent):
        self.update_remaining_after_removing_order(order_failed_event.order_id, 'fail')
```
(Explain what is happening on the code above)