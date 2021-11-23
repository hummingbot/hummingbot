---
tags:
- market making
- dex strategy
---

# `uniswap_v3_lp`

!!! note
    This is a proof-of-concept strategy that demonstrates how to dynamically maintain Uniswap-V3 positions as market prices changes. More features will be added over time based on community feedback.

## 📁 [Strategy folder](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/uniswap_v3_lp)

## 📝 Summary

This strategy creates and maintains Uniswap positions as the market price changes in order to continue providing liquidity. Currently, it does not remove or update positions.

## 🏦 Exchanges supported

[`uniswap-v3`](/exchanges/uniswap-v3)

## 👷 Maintainer

* Release added: [0.40.0](/release-notes/0.40.0/) by CoinAlpha
* Maintainer: CoinAlpha

## 🛠️ Strategy configs

[Config map](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/uniswap_v3_lp/uniswap_v3_lp_config_map.py)

| Parameter                    | Type        | Default     | Prompt New? | Prompt                                                 |
|------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `market`                     | string      |             | True        | Enter the trading pair you would like to provide liquidity on [connector]|
| `fee_tier`                   | string      |             | True        | On which fee tier do you want to provide liquidity on? (LOW/MEDIUM/HIGH)|
| `buy_spread`                 | decimal     |  1.00       | True        | How far away from the mid price do you want to place the buy position? (Enter 1 to indicate 1%)|
| `sell_spread`                | decimal     |  1.00       | True        | How far away from the mid price do you want to place the sell position? (Enter 1 to indicate 1%)|
| `base_token_amount`          | decimal     |             | True        | How much of your base token do you want to use for the buy position? |
| `quote_token_amount`         | decimal     |             | True        | How much of your quote token do you want to use for the sell position? |
| `min_profitability`          | decimal     |             | True        | What is the minimum profitability for each position is be adjusted? (Enter 1 to indicate 1%)|
| `use_volatility`             | bool        |  False      | False       | Do you want to use price volatility to adjust spreads? (Yes/No)| 
| `volatility_period`          | int         |  1          | False       | Enter how long (in hours) do you want to use for price volatility calculation |
| `volatility_factor`          | decimal     |  1.00       | False       | Enter the multiplier applied to price volatility |

## 📓 Description

[Trading logic](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/uniswap_v3_lp/uniswap_v3_lp.py)

!!! note "Approximation only"
    The description below is a general approximation of this strategy. Please inspect the strategy code in **Trading Logic** above to understand exactly how it works.

### Starting

1. The bot will look for information about the pool, and if it is a valid pool. If the pool doesn't exist, warn the user and stop the strategy
3. Fetch the current mid price of the pool (`last_price`)
3. If `use_volatility` is True, the bot will calculate the price volatility used to widen spreads
4. If the pool is valid, the bot will create two starting positions:
    - The SELL position with:
        - Amount of tokens added to the position = `base_token_amount`
        - `upper_price` = `(1 + sell_spread) * last_price` 
        - `lower_price` = `last_price`
    - The BUY position with:
        - Amount of tokens added to the position = `quote_token_amount`
        - `upper_price` = `last_price`
        - `lower_price` = `(1 - buy_spread) * last_price`

![image.png](/assets/img/uniswap-v3-1.png)

The bot maintains a variable `total_position_range` that defines the total price range, comprised of `upper_price` and `lower_price`, where the bot is providing liquidity.

### Running

Each tick, the bot monitors the pool mid price (`last_price`) and compare it to the bounds of `total_position_range`. It will adjust the position under the following scenarios:

**`last_price` is higher than `upper_price` of `total_position_range`**

1. Create a new SELL liquidity position, using the following values:
    - Amount of tokens of the new position = `base_token_amount`
    - Top price bound = `(1 + sell_spread) * last_price`
    - Lower price bound = `last_price`
2. Update `total_position_range`: `upper_price = (1 + sell_spread) * last_price`

![image.png](/assets/img/uniswap-v3-2.png)

**`last_price` is lower than `lower_price` of `total_position_range`**

1. Create a new BUY liquidity position, using the following values:
    - Amount of tokens of the new position = `quote_token_amount`
    - New position upper price = `last_price`
    - New position lower price = `(1 - buy_spread) * last_price`
2. Update `total_position_range`: `lower_price = (1 - buy_spread) * last_price`

![image.png](/assets/img/uniswap-v3-3.png)

### Important Notes

- Currently, the strategy does not remove existing positions. The user should do it manually through the Uniswap interace (https://app.uniswap.org/#/pool).
- The `status` command shows the current profitability of each position, using the `quote` asset as reference