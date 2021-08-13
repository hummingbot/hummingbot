# Terra

The [Terra Protocol](https://terra.money/) is the creator of the Luna Token, Terra Core, and the blockchain payment solution CHAI. The design of the Terra Protocol is based on two things: stability and adoption by e-commerce platforms.

It runs on a Tendermint Delegated Proof of Stake algorithm and Cosmos SDK. It is aimed at becoming a new worldwide financial infrastructure on which different DApps can be created.

Source: https://medium.com/stakin/what-is-terra-money-8eb1dcb314d2

!!! warning
    Currently, [Terra](/protocol-connectors/terra) could not be used on Binary Installers since it would need a [gateway](https://docs.hummingbot.io/gateway/installation/#what-is-hummingbot-gateway) connection for it to work. It can only be used when running Hummingbot from source or with Docker.

## Prerequisites

- Hummingbot Gateway (see [installation guide](/gateway/installation/))
- Terra wallet

## Creating a Terra wallet

1. Download and install Terra Station wallet from their site https://terra.money/
2. Launch Terra Station and click the **Connect** button at the top
3. Select **New wallet** to create a new wallet
4. Fill out all forms and make sure to store your seed phrase in a secured place
5. Confirm your seed to complete
6. The Terra wallet address is located at the top

![](/assets/img/terra-create-wallet.gif)

## Connecting to Terra

!!! note
    Before connecting your wallet address and seed, make sure to have Terra set up when you create your `gateway-instance`

![](/assets/img/terra_setup.png)

1. Run the command `connect terra` in the Hummingbot client
2. Enter your Terra wallet address
3. Enter your Terra wallet seed, including the spaces in between each word
4. Create and run an `amm_arb` strategy to use the Terra connector

![](/assets/img/connect-terra.gif)
