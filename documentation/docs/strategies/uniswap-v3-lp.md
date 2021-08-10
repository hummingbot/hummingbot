# Uniswap v3 Liquidity Pool Strategy

**Updated as of v0.40**

Before you can use the Uniswap v3 LP Strategy in Hummingbot, you need to install and configure the [Gateway API server](/gateway/installation).

The flowchart below is a guide on how to set up the installation and configuration of the strategy.

![Uniswap v3 LP Strategy](/assets/img/uniswapv3-strat-diagram.jpg)

### Setup Ethereum wallet and nodes

Ensure you have setup the Ethereum wallet and nodes, for more details:

- see [Setup Ethereum Wallet](https://docs.hummingbot.io/operation/connect-exchange/#setup-ethereum-wallet)
- see [Setup Infura Node](https://docs.hummingbot.io/operation/connect-exchange/#option-1-infura). Take note of the Ethereum RPC URL to be use later for Gateway Docker settings.

### Setup gateway

You need to setup the [Gateway](/gateway/installation) to use this strategy.

## Uniswap v3 LP Strategy iteration 1 behaviour

The bot will create two liquidity positions:

### Buy-side

- The upper price bound of this position is as close as possible to the current market price
- The lower price bound of this position is set by the spread defined by the user (A)
- The amount of tokens locked on this position is the amount defined on the quote amount question (D)

### Sell-side

- The lower price bound of this position is as close as possible to the current market price
- The upper price bound of this position is set by the spread defined by the user (B)
- The amount of tokens locked on this position is the amount defined on the base amount question (C)

## Uniswap v3 Strategy

The following example shows a step-by-step on configuring the strategy.

1. In Hummingbot, enter `create`.

2. Enter `uniswap_v3_lp`.
```json
What is your market making strategy?
>>> uniswap_v3_lp
```

3. 
```json
Enter the pair you would like to provide liquidity to (e.g. WETH-DAI)
>>> WETH-DAI
```

4. 
```json
On which fee tier do you want to provide liquidity on? (LOW/MEDIUM/HIGH)
>>> Medium
```

5. 
```json
How wide apart(in percentage) do you want the lower price to be from the upper price for buy position? (Enter 1 to indicate 1%)
>>>
```

6. 
```json
How wide apart(in percentage) do you want the lower price to be from the upper price for sell position? (Enter 1 to indicate 1%)
>>>
```

7. 
```json
How much of your base token do you want to use?
>>>
```

8. 
```json
How much of your quote token do you want to use?
>>>
```

!!! note
    `Paper_trade` is not applicable for this strategy. Alternatively, you may set up a `kovan_testnet` to help you run some tests without risking funds.
