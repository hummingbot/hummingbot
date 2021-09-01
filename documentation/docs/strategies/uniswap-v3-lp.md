**Updated as of v0.43**

## How it works

!!! note
    This is a proof-of-concept strategy that demonstrates how to dynamically maintain Uniswap-V3 positions as market prices changes. More features will be added over time based on community feedback.

This strategy creates and maintains Uniswap positions as the market price changes in order to continue providing liquidity. Currently, it does not remove or update positions.

## Strategy files

**Folder**: https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/strategy/uniswap_v3_lp
**Template**: https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/templates/conf_uniswap_v3_lp_strategy_TEMPLATE.yml

## Parameters

**Config map**: https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/uniswap_v3_lp/uniswap_v3_lp_config_map.py

| Parameter                    | Type        | Default     | Prompt New? | Prompt                                                 |
|------------------------------|-------------|-------------|-------------|--------------------------------------------------------|
| `market`                     | string      |             | True        | Enter the pair you would like to provide liquidity to  |
| `fee_tier`                   | string      |             | True        | On which fee tier do you want to provide liquidity on? (LOW/MEDIUM/HIGH)|
| `buy_position_price_spread`  | decimal     |  1.00       | True        | How wide apart(in percentage) do you want the lower price to be from the upper price for buy position?(Enter 1 to indicate 1%)|
| `sell_position_price_spread` | decimal     |  1.00       | True        | How wide apart(in percentage) do you want the lower price to be from the upper price for sell position? (Enter 1 to indicate 1%)|
| `base_token_amount`          | decimal     |             | True        | How much of your base token do you want to use?        |
| `quote_token_amount`         | decimal     |             | True        | How much of your quote token do you want to use?       |
| `min_profitability`          | decimal     |             | True        | What minimum profit do you want each position to have before they can be adjusted? (Enter 1 to indicate 1%)|
| `use_volatility`             | bool        |  False      | False       | Do you want to use price volatility from the pool to adjust spread for positions? (Yes/No)| 
| `volatility_period`          | int         |  1          | False       | Enter how long (in hours) do you want to use for price volatility calculation|
| `volatility_factor`          | decimal     |  1.00       | False       | Enter volatility factor                                |

## Prerequisites

- [Gateway API server](/installation/gateway/)
- [Ethereum Wallet](/operation/connect-exchange/#setup-ethereum-wallet)
- [Infura Node](/operation/connect-exchange/#option-1-infura)


## Specification

!!! tip "To Do"
    Match description and images below to [the strategy file](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/strategy/uniswap_v3_lp/uniswap_v3_lp.py). Each tick, the strategy 1) determines if the connector if ready, 2) calculates volatility if it is used, and 3) generates new positions if `total_position_range` has widened based on price movements

**Prompts:**

- Enter the trading pair and fee tier of the pool
- Top price bound (in %) relative to market price (`sell_position_price_spread`)
- Lower price bound (in %) relative to market price (`buy_position_price_spread`)
- Base token amount to add (`base_token_amount`)
- Quote token amount to add (`quote_token_amount`)
- Bot will calculate `top_bound_price` and `lower_bound_price` based on the current `market_price` and the spreads entered by the user

**Starting the strategy**

- Enter `start`
- The bot will look for information about the pool, and if it is a valid pool
  - If the pool doesn't exist, warn the user and stop the strategy
- If the pool is valid, the bot will create two starting positions:
  1. The sell position with:
      - Amount of tokens added to the position = `base_token_amount`
      - Top price bound = `top_bound_price`
      - Lower price bound = current market price
  2. The buy position with:
      - Amount of tokens added to the position = `quote_token_amount`
      - Top price bound = current market price
      - Lower price bound = `lower_bound_price`

![image.png](/assets/img/uniswap-v3-1.png)

**As the strategy is running**

The bot will monitor the current price of the pool, with two possible conditions to trigger a new position creation:

1. Price goes above `top_bound_price`
```python
if market_price > top_price_bound
  new_position_top_price = market_price + (market_price * top_bound_spread)
  new_position_lower_price = market_price
  new_position_size = base_token_amount
  create_new_position(new_position_top_price, new_position_lower_price, new_position_size)
  top_bound_price = new_position_top_price // The new upper bound becomes the upper bound of the new position
```
![image.png](/assets/img/uniswap-v3-1.png)


2. Price goes below `lower_bound_price`
```python
if market_price < lower_bound_price
  new_position_top_price = market_price
  new_position_lower_price = market_price - (market_price * lower_bound_spread)
  new_position_size = base_token_amount
  create_new_position(new_position_top_price, new_position_lower_price, new_position_size)
  lower_bound_price = new_position_lower_price // The new lower bound becomes the upper bound of the new position
```
![image.png](/assets/img/uniswap-v3-1.png)
