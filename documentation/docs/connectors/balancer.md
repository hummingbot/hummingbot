# Balancer

Balancer is an automated portfolio manager, liquidity provider, and price sensor. In other words, a decentralized finance protocol based on Ethereum allows automatic market-making.

!!! warning
    Currently, [Balancer](/connectors/balancer) could not be used on Binary Installers since it would need a [gateway](https://docs.hummingbot.io/gateway/installation/#what-is-hummingbot-gateway) connection for it to work. It can only be used when running Hummingbot from source or with Docker

## Prerequisites

- Ethereum wallet (refer to our guide [here](/operation/connect-exchange/#setup-ethereum-wallet))
- Ethereum node (refer to our guide [here](/operation/connect-exchange/#setup-ethereum-nodes))
- Hummingbot Gateway (done after connecting to Balancer)
- Some ETH in wallet for gas
- Inventory on both base and quote assets for the connectors

## Connecting to Balancer

When creating Hummingbot Gateway, it picks up the Ethereum settings in the global config file, which we can set up in the Hummingbot client.

1. Run the command `connect ethereum` in the Hummingbot client
2. Enter your wallet private key
3. Enter Ethereum node address (starts with https://)
4. Enter the WebSocket connection address of your Ethereum node (starts with wss://)

![](/assets/img/connect-ethereum.gif)

## Install Hummingbot Gateway

After adding your Ethereum wallet and node in Hummingbot, follow the guide in the link below on how to install Hummingbot Gateway.

- [Hummingbot Gateway Installation](/gateway/installation/)

!!! note
    For setting up gas estimator, you can check our [ETH Gas Station](/gateway/installation/#eth-gas-station) for more info

