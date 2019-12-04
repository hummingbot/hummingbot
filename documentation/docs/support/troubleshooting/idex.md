# IDEX Error Messages

Common errors found in logs when running Hummingbot on IDEX connector.

!!! note
    Hummingbot should run normally regardless of these errors. If the bot fails to perform or behave as expected (e.g. placing and cancelling orders, performing trades, stuck orders, orders not showing in exchange, etc.) you can get help through our [support channels](/support/index).

You may see any of these errors in logs when trading on IDEX market. These are server-side issues on IDEX's end.

```
OSError: Error fetching data from https://api.idex.market/order.

HTTP status is 400 - {'error': "Cannot destructure property `tier` of 'undefined' or 'null'."}
HTTP status is 400 - {'error': 'Unauthorized'}
HTTP status is 400 - {'error': 'Nonce too low. Please refresh and try again.'}
HTTP status is 500 - {'error': 'Something went wrong. Try again in a moment.'}
```

