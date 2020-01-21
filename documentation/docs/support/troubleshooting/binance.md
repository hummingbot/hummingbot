# Binance Error Messages

Common errors found in logs when running Hummingbot on Binance connector.

!!! note
    Hummingbot should run normally regardless of these errors. If the bot fails to perform or behave as expected (e.g. placing and cancelling orders, performing trades, stuck orders, orders not showing in exchange, etc.) you can get help through our [support channels](/support/index).

These are known issues from the Binance API and Hummingbot will attempt to reconnect afterwards.

```
hummingbot.market.binance.binance_market - NETWORK - Unexpected error while fetching account updates.

AttributeError: 'ConnectionError' object has no attribute 'code'
AttributeError: 'TimeoutError' object has no attribute 'code'

hummingbot.core.utils.async_call_scheduler - WARNING - API call error:
('Connection aborted.', OSError("(104, 'ECONNRESET')",))

hummingbot.market.binance.binance_market - NETWORK - Error fetching trades update for the order
[BASE][QUOTE]: ('Connection aborted.', OSError("(104, 'ECONNRESET')",)).
```


## APIError (code=-1021)

Timestap errors in logs happen when the Binance clock gets de-synced from time to time as they can drift apart for a number of reasons. Hummingbot should safely recover from this and continue running normally.

```
binance.exceptions.BinanceAPIException: APIError(code=-1021): Timestamp for this request is outside of the recvWindow.
```

## APIError (code=-1003)

Weight/Request error in logs happens when it encountered a warning or error and Hummingbot repeatedly sends the request (fetching status updates, placing/canceling orders, etc.) which resulted to getting banned. This should be lifted after a couple of hours or up to a maximum of 24 hours.

* Too many requests queued.
* Too much request weight used; please use the websocket for live updates to avoid polling the API.
* Too much request weight used; current limit is %s request weight per %s %s. Please use the websocket for live updates to avoid polling the API.
* Way too much request weight used; IP banned until %s. Please use the websocket for live updates to avoid bans.

```
binance.exceptions.BinanceAPIException: APIError(code=-1003): Way too much request weight used; IP banned until 1573987680818. Please use the websocket for live updates to avoid bans
```

For more information visit the Binance API documentation for [Error Codes](https://binance-docs.github.io/apidocs/spot/en/#error-codes-2).
	
## HTTP status 429 and 418 return codes

The [HTTP return codes](https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#http-return-codes) in Binance official API docs includes information on each code.

We recommend to refrain from running multiple Hummingbot instances trading on Binance in one server or IP address. Otherwise, it may result to these errors especially if using multiple orders mode with pure market making strategy.

If you use the endpoint https://api.binance.com/api/v3/exchangeInfo you can see their limitation on API trading.

```
"timezone": "UTC",
"serverTime": 1578374813914,
"rateLimits": [
    {
        "rateLimitType": "REQUEST_WEIGHT",
        "interval": "MINUTE",
        "intervalNum": 1,
        "limit": 1200
    },
    {
        "rateLimitType": "ORDERS",
        "interval": "SECOND",
        "intervalNum": 10,
        "limit": 100
    },
    {
        "rateLimitType": "ORDERS",
        "interval": "DAY",
        "intervalNum": 1,
        "limit": 200000
    }
```

Exceeding the 1,200 total request weight per limit will result in an IP ban. The order limits of 100 per second or 200,000 will be dependent on account.