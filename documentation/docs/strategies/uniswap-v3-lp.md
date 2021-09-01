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

On each tick, the strategy:
1) Determines if the connector is ready,
2) Creates the initial *BUY* and *SELL* positions, if there isn't any 
3) Creates a new liquidity position if the pool price moved above the `upper_bound` OR below the `lower_bound` values.

**Prompts:**

`Enter the pair you would like to provide liquidity to`: 
> Defines the Liquidity pool asset pair (`market`)
> 
> **Note:** The order or the assets matters to properly identify the correct pool. Make sure to check https://info.uniswap.org/#/ for the correct asset order

`On wich fee tier do you want to provide liquidity on? (LOW/MEDIUM/HIGH)`
> Defines the trading fee of the pool you want to provide liquidity (`fee_tier`). Fee tiers are:
>  
> LOW = 0.05%
> MEDIUM = 0.30%
> HIGH = 1.00%
> 
> **Note:** Each fee tier is a different uniswap pool 

`How wide apart (in percentage) do you want the lower price to be from the upper price for the BUY position?`
> Defines `buy_position_price_spread`
> 
> The value is used to calculate the lower price bound:
> `lower_price = (1 - buy_spread) * last_price`

`How wide apart (in percentage) do you want the upper price to be from the lower price for the SELL position?`
> Defines `sell_position_price_spread`
> 
> The value is used to calculate the upper price bound:
> `upper_price = (1 + sell_spread) * last_price`

`How much of the base token do you want to use?`
> Defines `base_token_amount`
> 
> This is the amount of tokens that will be added to the SELL positions

`How much of the quote token do you want to use?`
> Defines `quote_token_amount`
> 
> This is the amount of tokens that will be added to the BUY positions

## Strategy Logic

**Starting the strategy**

- Enter `start`
- The bot will look for information about the pool, and if it is a valid pool
  - If the pool doesn't exist, warn the user and stop the strategy
- If the pool is valid, the bot will create two starting positions:
  1. The SELL position with:
      - Amount of tokens added to the position = `base_token_amount`
      - Top price bound = `upper_price`
      - Lower price bound = `last_price`
  2. The buy position with:
      - Amount of tokens added to the position = `quote_token_amount`
      - Top price bound = `last_price`
      - Lower price bound = `lower_price`

![image.png](/assets/img/uniswap-v3-1.png)

**As the strategy is running**

Every tick, the bot will monitor the current price of the pool (`last_price`), with two possible conditions to trigger a new position creation:

1. Price goes above `upper_price`

 - A new SELL liquidity position will be created, using the following values:

    - Amount of tokens of the new position = `base_token_amount`
    - New position upper price = `(1 + sell_spread) * last_price`
    - New position lower price = `last_price`
 - The `upper_price` value will be redefined 
    - `upper_price = (1 + sell_spread) * last_price`
 - The `lower_price` value won't be changed

![image.png](/assets/img/uniswap-v3-2.png)

2. Price goes below `lower_price`

 - A new BUY liquidity position will be created, using the following values:

    - Amount of tokens of the new position = `quote_token_amount`
    - New position upper price = `last_price`
    - New position lower price = `(1 - buy_spread) * last_price`
 - The `lower_price` value will be redefined 
    - `lower_price = (1 - buy_spread) * last_price`
 - The `upper_price` value won't be changed

![image.png](/assets/img/uniswap-v3-3.png)

**Important Notes**

- The strategy WILL NOT remove existing liquidity positions. The user must do it manually through the Uniswap front-end (https://app.uniswap.org/#/pool)
- The `status` command will show what is the current profit of each position, using the `quote` asset as reference