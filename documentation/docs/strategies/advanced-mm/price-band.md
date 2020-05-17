# Price Band

**Updated as of `v0.27.0`**

This feature allows you to set a price band within which your bot places both buy and sell orders normally.

## How It Works

`price_ceiling` and `price_floor` are two optional parameters that you can set. By default, these parameters have a value of -1, which means that they are not used.

Type `config price_ceiling` and `config price_floor` to set values for these parameters. If the price exceeds `price_ceiling`, your bot only places sell orders. If the price falls below `price_floor`, your bot only places buy orders.

## Relevant Parameters

| Parameter | Prompt | Definition |
|-----------|--------|------------|
| `price_ceiling` | `Enter the percent change in price needed to refresh orders at each cycle` | The spread (from mid price) to defer order refresh process to the next cycle. |
| `price_floor` | `Enter the percent change in price needed to refresh orders at each cycle` | The spread (from mid price) to defer order refresh process to the next cycle. |
