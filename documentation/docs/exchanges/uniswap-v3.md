# Uniswap v3

[Uniswap](https://uniswap.org/) is a protocol on Ethereum for swapping ERC20 tokens. Unlike most exchanges, which are designed to take fees, Uniswap is designed to function as a public good — a tool for the community trade tokens without platform fees or middlemen. 

This connector integrates with Uniswap V3, which introduces concentrated liquidity and multiple fee tiers as new features, giving liquidity providers more control.

Source: https://docs.uniswap.org/protocol/concepts/V3-overview/concentrated-liquidity

!!! warning
    Currently, [Uniswap](/connectors/uniswap/) could not be used on Binary Installers since it would need a [gateway](/installation/gateway) connection for it to work. It can only be used when running Hummingbot from source or with Docker.

## Prerequisites

- Ethereum wallet (refer to our guide [here](/operation/connect-exchange/#setup-ethereum-wallet))
- Ethereum node (refer to our guide [here](/operation/connect-exchange/#setup-ethereum-nodes))
- Hummingbot Gateway (done after connecting to Uniswap)
- Some ETH in wallet for gas
- Inventory on both base and quote assets for the connectors

## Connecting to Uniswap

When creating Hummingbot Gateway, it picks up the Ethereum settings in the global config file which we can set up in the Hummingbot client.

1. Run the command `connect ethereum` in the Hummingbot client
2. Enter your wallet private key
3. Enter Ethereum node address (starts with https://)
4. Enter the websocket connection address of your Ethereum node (starts with wss://)

![](/assets/img/connect-ethereum.gif)

## Install Hummingbot Gateway

After adding your Ethereum wallet and node in Hummingbot, follow the guide in the link below on how to install Hummingbot Gateway.

- [Hummingbot Gateway Installation](/installation/gateway)
