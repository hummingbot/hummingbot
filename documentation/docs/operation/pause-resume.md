# Pause and Resume Strategy

This feature allows users to pause a running strategy using the command `exit --suspend`. This allows the bot to stop while keeping the hanging orders in the order book. To resume, run the command `start --restore`.

!!! note
    Currently, this feature only works with pure market making strategy.

## Pause

The `exit --suspend` command will "pause" the strategy and exit the hummingbot client. All active orders will become hanging orders while hanging orders will stay hanging when resumed at a later time.

This could be an advantage if you don’t want to cancel orders but want to exit the bot.

![Pause](/assets/img/Pause.png)

## Resume

To resume a "paused" strategy, import the config file and run the command `start --restore`. It will create new sets of active orders on top of the hanging orders from when it was paused.

![Resume](/assets/img/Resume.png)

!!! note
    After running `start --restore` spreads may change once the bot brings back your orders, it will display what the current spreads of your order.

You can see that when we use `exit --suspend` it exits the bot. When you run `start --restore` all active orders became hanging orders. Refer to the example below.

![](/assets/img/pause-and-resume.gif)

## Important notes

Always use `start --restore` when resuming a paused strategy. Accidentally running the `start` command after importing the config file will cancel all of its dangling orders and start the strategy from a fresh state. See example below,

These are the orders before we run `exit --suspend`

```
Orders:
   Level  Type  Price Spread Amount (Orig)  Amount (Adj)       Age
       2  sell 0.3401  0.59%          46.0            46  00:00:03
       1  sell 0.3398  0.50%          45.0            45  00:00:03
```

You will notice that when we use `start` it will show on the logs that orders are cancelled.
![](/assets/img/exit-suspend.gif)

!!! note
    Running `start --restore` on a different configuration file wont work, You should always use the same config file where the `exit --suspend` is executed.
