# Uniswap v3

[Uniswap](https://uniswap.org/) is a protocol on Ethereum for swapping ERC20 tokens. Unlike most exchanges, which are designed to take fees, Uniswap is designed to function as a public good — a tool for the community trade tokens without platform fees or middlemen.

Concentrated liquidity and multiple fee tiers are the new features behind Uniswap v3, giving the liquidity provider more control of risk and assets.

Source: https://decrypt.co/resources/what-is-uniswap

!!! warning
    Currently, [Uniswap](/protocol-connectors/uniswap/) could not be used on Binary Installers since it would need a [gateway](https://docs.hummingbot.io/gateway/installation/#what-is-hummingbot-gateway) connection for it to work. It can only be used when running Hummingbot from source or with Docker.

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

- [Hummingbot Gateway Installation](/gateway/installation/)

!!! note
    For setting up gas estimator, you can check our [ETH Gas Station](/gateway/installation/#eth-gas-station) for more info

## Confirm connection

Check the connection of Uniswap v3 and gateway.

[Open and access gateway](/gateway/installation/#install-gateway-via-source) **global_conf.yml** with a text editor.

Make sure the value of the connections for Uniswap v3 below are open and ended with double quotation marks (**""**) in your **global_conf.yml**.

- UNISWAP_ROUTER
- UNISWAP_V3_CORE
- UNISWAP_V3_ROUTER
- UNISWAP_V3_NFT_MANAGER

```
# UNISWAP_V3_CORE is deployed at 0x1F98431c8aD98523631AE4a59f267346ea31F984 on the Ethereum mainnet, and the Ropsten, Rinkeby, Görli, and Kovan testnets.
# UNISWAP_V3_ROUTER is deployed at 0xE592427A0AEce92De3Edee1F18E0157C05861564 on the Ethereum mainnet, and the Ropsten, Rinkeby, Görli, and Kovan testnets.
# UNISWAP_V3_NFT_MANAGER is deployed at 0xC36442b4a4522E871399CD717aBDD847Ab11FE88 on the Ethereum mainnet, and the Ropsten, Rinkeby, Görli, and Kovan testnets.

UNISWAP_ROUTER: "0x7a250d5630B4cF539739dF2C5dAcB4c659F2488D"
UNISWAP_V3_CORE: "0x1F98431c8aD98523631AE4a59f267346Ea31F984"
UNISWAP_V3_ROUTER: "0xE592427A0AEce92De3Edee1F18E0157c05861564"
UNISWAP_V3_NFT_MANAGER: "0xC36442b4a4522E871399CD717aBDD847AB11FE88"
```
