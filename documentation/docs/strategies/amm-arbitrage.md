# AMM Arbitrage

**Updated as of v0.33**

Before you can use the AMM arbitrage strategy in Hummingbot, you need to install and configure the Gateway API server. The following flowchart shows the typical installation and configuration process for Balancer.

![Balancer flowchart](/assets/img/balancer-flowchart.png)

### Setup Ethereum wallet and nodes

Ensure you have set up the Ethereum wallet and nodes for more details:

- see [Setup Ethereum Wallet](https://docs.hummingbot.io/operation/connect-exchange/#setup-ethereum-wallet)
- see [Setup Infura Node](https://docs.hummingbot.io/operation/connect-exchange/#option-1-infura). Take note of the Ethereum RPC URL to be used later for Gateway Docker settings.

## AMM Arbitrage Strategy

After the installation and configuration are completed, we can create the configuration for the AMM arbitrage strategy. The following example shows a step-by-step on configuring the AMM arb strategy.

!!! note
    `Paper_trade` is not applicable for this strategy. Alternatively, you may set up a `kovan_testnet` to help you run some tests without risking funds.

1. In Hummingbot, enter `create`.
2. Enter `amm-arb`.
3. Enter `balancer`.
4. Enter the first trading pair, for example, `BAT-DAI`.

!!! note
    Ensure the trading pair tokens are in your wallet to trade.

5. Enter an exchange connector, for example, `binance`.
6. Enter the second trading pair, for example, `BAT-USDT`.
7. Follow on-screen prompts and info for AMM arb parameters.
8. Enter `start` to run the strategy.
9. To check transactions, you can use etherscan.io to check if any pending transaction gets stuck for too long (> 5 min). If any Tx got stuck, change the `config ethgasstation_gas_level` to fast, the transaction setting should complete < 1-2 min

For details on each AMM parameter, see the following sections for details. These parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/amm_arb_[#].yml`).

### `connector 1`

Enter the first exchange/AMM you would like to trade on.

** Prompt: **

```json
Enter your first spot connector (Exchange/AMM)
>>>
```

### `market_1`

Enter the first token trading pair for the secondary exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on balancer (e.g. WETH-DAI)
>>> WETH-DAI
```

### `connector 2`

Enter the secondary exchange/AMM you would like to trade on.

** Prompt: **

```json
Enter your second spot connector (Exchange/AMM)
>>>
```

### `market_2`

Enter the second token trading pair for the secondary exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on balancer (e.g. ZRX-ETH)
>>> ZRX-ETH
```

### `order_amount`

The order amount for the bid order of the base asset for the first trading pair.

** Prompt: **

```json
What is the amount of [first trading pair base asset] per order?
>>>
```

### `min_profitability`

Minimum profitability target required to execute trades.

** Prompt: **

```json
What is the minimum profitability for you to make a trade? (Enter 1 to indicate 1%) >>>
>>> 3
```

### `market_1_slippage_buffer`

Percent buffer added to the market 1 exchange price to account for price movement before trade execution.

** Prompt: **

```json
How much buffer do you want to add to the price to account for slippage for orders on the first market (Enter 1 to indicate 1%) >>>"
>>> 3
```

### `market_2_slippage_buffer`

Percent buffer added to the market two exchange price to account for price movement before trade execution.

** Prompt: **

```json
How much buffer do you want to add to the price to account for slippage for orders on the second market (Enter 1 to indicate 1%) >>>
>>> 3
```

### `concurrent_orders_submission`

If true, the bot submits both arbitrage taker orders (buy and sell) simultaneously.
If false, the bot will wait for the first exchange order filled before submitting the other order.

** Prompt: **

```json
Do you want to submit both arb orders concurrently (Yes/No)? If no, the bot will wait for the first connector order filled before submitting the other order >>>
>>> Yes
```

### `manual_gas_price`

If you prefer to manually set your gas other than using Defipulse.

!!! note
    If Defipulse is set for gas estimation, manual_gas_price is ignored. To use `manual gas price`, you need to disable `ethgasstation_gas_enabled`

** Prompt: **

```json
Enter fixed gas price (in Gwei) you want to use for Ethereum transactions
>>>
```

## Rate oracle integration

- Make sure gateway is properly running together with Hummingbot client.

- You can initially setup `rate_oracle_source` and get the rates before creating the AMM-Arbritrage strategy.

![Rate Oracle Config](/assets/img/rate-oracle-ammarb-config.png)

![Rate Oracle Status](/assets/img/rate_oracle_amm_arb_status.png)

## Switch Balancer network

Two ways to switch network [Ethereum mainnet/Kovan testnet](https://docs.hummingbot.io/gateway/installation/#setting-up-kovan-testnet)

1. Delete the Gateway docker container and re-run the `create-gateway.sh` script.
2. Use the `update-gateway.sh` script to update the docker image and follow the prompt instructions.
