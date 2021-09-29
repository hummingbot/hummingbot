# Rate Limits Share Pct

Some exchanges impose rate limits per account. When running multiple bots using a single account, `rate_limits_share_pct` users to set a certain percentage of the total limit to each instance. When the bot is near the allocated limit, Hummingbot sends a notification as a warning so users can adjust their configuration before the account is banned.

For example, the rate limit for AscendEX is 100 requests per second. Your account will be banned for a certain period of time if you keep hitting the rate limit in 10 minutes (status code `429` or `100014`).

Setting 50% for `rate_limits_share_pct` means we want the bot to send a notification when it starts to send 50 requests per second for that specific instance.

## How to use the parameter

1. Run `config rate_limits_share_pct` while the strategy is stopped
2. Enter the percentage of API rate limit you want to allocate to the bot
![](/assets/img/rate-limits-share-pct-prompt.png)
3. Start the strategy using `start` command
4. A notification will be displayed in the output pane when the `rate_limits_share_pct` value is about to be reached
![](/assets/img/rate-limits-share-pct-message.png)

!!! note
    You can also configure this setting while the strategy is running. However, the strategy must be restarted for the changes to take effect.
