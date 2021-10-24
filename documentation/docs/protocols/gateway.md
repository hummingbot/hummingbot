!!! note
    Gateway is currently being refactored as part of the [Gateway V2 redesign](/developers/gateway). The current V1 version is working, but may have usability issues that will be addressed in the redesign.

## What is Hummingbot Gateway?

Hummingbot Gateway is API middleware that allows Hummingbot to connect to decentralized exchanges on various blockchain protocols that are used in the [amm-arb strategy](/strategies/amm-arbitrage/) and other strategies. Essentially, Gateway is a light web server that enables Hummingbot client to send and receive data from different blockchain protocols and provides an easier entry point for external devs to build connectors to other protocols.

!!! note
    To use Gateway, you need to install Hummingbot using Docker or from source. Gateway doesn't work with the binary installers.

## Create SSL certificates

1. Run the command `gateway generate_certs` in the Hummingbot client
2. Enter a passphrase to be used later during installation

![](/assets/img/generate_certs.gif)

!!! note
    As this passphrase will be stored in unencrypted form in the Gateway environment, we recommend that you use a different password as the Hummingbot password, which is used to encrypt your API and private keys.

## Install Gateway via Docker

1. Take note of the absolute path where your Hummingbot files are stored. You can run the command `pwd` from the terminal while inside the folder.
2. Copy and paste the following commands to your terminal:

### Mac

```Mac
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create-gateway.sh -o create-gateway.sh
curl https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update-gateway.sh -o update-gateway.sh
chmod a+x *.sh
./create-gateway.sh
```

### Linux

```Linux
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create-gateway.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update-gateway.sh
chmod a+x *.sh
./create-gateway.sh
```

It downloads the scripts from GitHub, sets their correct permission and runs the `create-gateway` script.

3. Answer each prompt, review the summary and enter **Y** to proceed with the installation.

![](/assets/img/gateway-2.gif)

!!! note
    When creating a Gateway instance for Ethereum protocol connectors such as [Balancer](/exchanges/balancer/), [Uniswap](/exchanges/uniswap/), and [Perpetual Finance](/exchanges/perp-fi/) the script picks up the settings from your global config file (`conf_global.yml`). Make sure to connect them first from the Hummingbot client before installing Gateway.

By default, Gateway will install on port `5000` which Hummingbot will connect to. If the default port is not available, Gateway will find the next port number.

4. The file `global_conf.yml` is created where your Gateway settings are saved.

## Configure port number (optional)

In case the port number used by Gateway is not set to the default value of `5000`, make sure to set the `gateway_api_port` in the Hummingbot client to match the same port number.

![](/assets/img/gateway-port-5001.png)

1. Run command `config gateway_api_port` in the Hummingbot client
2. Enter the port number indicated when Gateway was created

![](/assets/img/config-gateway-api-port.gif)

## ETH Gas Station

!!! note
    As of version 0.38.0, ethgasstation_gas_enabled has been removed from the hummingbot client and added to the parameters when setting up gateway.

Users have the option to use and configure DeFI Pulse gas price as the gas estimator.

1. Sign up for a free account on [DeFi Pulse Data](https://data.defipulse.com)
2. Get your API key - once you log into DeFi Pulse Data, your API key can be found on the right side of the Dashboard. Click the copy button to copy your API Key.

![](/assets/img/defipulse-2.png)

When setting up your Hummingbot gateway, you will be ask if you want to enable ETH Gas price. If yes,

1. You would need to enter the DeFI pulse API key
2. Enter gas level you want to use for ETH transactions
3. Refresh time for ETH gas price look up

![](/assets/img/ethgas-yes.png)

If you choose not to enable ETH gas price, you would only need to set up the fixed gas price to use for ETH transactions.

![](/assets/img/ethgas-no.png)

## Update Gateway via Docker

To update the docker container, run the `update-gateway.sh` script and and follow the prompt instructions. The update script allows you to stop and delete the running instance, and update the docker image if it is not the latest. Upon completion, it will automatically execute the create-gateway.sh script to create a new Gateway container instance.

## Install Gateway from source

### Prerequisites

Installation applies to Windows, Linux or macOS

1. NodeJS - visit this [page](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm/) to download and install.

- Tested versions `v12.13.0, v12.13.1`.

```bash
# to check your current version
node -v
```

![](/assets/img/gw_version.gif)

!!! tip
    You can install [nvm](https://gist.github.com/d2s/372b5943bce17b964a79) to manage and use different node versions on the same system.

2. Yarn (required for node package installations)

```bash
# to install yarn globally
npm -g install yarn
```

- Tested versions `v1.22.5 and v1.22.10`

### Setup

Steps for setting up gateway-api

```bash
# clone the repo
git clone https://github.com/CoinAlpha/gateway-api
```

```bash
# open directory
cd gateway-api
```

```bash
# install npm packages
# build packages
yarn
yarn build
```

![](/assets/img/gw_yarn.gif)

```bash
# copy sample environment
cp global_conf.yml.example global_conf.yml
```

![](/assets/img/gw_env.gif)

- Edit `global_conf.yml` file with your favorite text editor then save changes.
- There are 2 ways to start the gateway

```bash
# run debug mode with additional route debug logging
yarn debug
```

```bash
# run prod mode
yarn start
```

![](/assets/img/gw_starting.gif)

## Setting up Kovan testnet

This guide will help you setup gateway-api instance for Kovan testnet. This will help you run some test to AMM_Arbitrage strategy without risking your funds.

You must have set your ETH wallet to Kovan test network, for metamask you can click the `Ethereum Mainnet` and select `Kovan Test Network`. To get test assets, you can go to https://gitter.im/kovan-testnet/faucet and login your github account. Provide your ETH wallet address.

![](/assets/img/kovan-metamask.PNG)

!!! tip
    Assets sent to your ETH wallet from kovan-testnet are not real (mainnet) ETH, has no market value, and is only useful for testing.

When connecting your Hummingbot to ethereum, you need to change to `kovan` instead of mainnet for your ethreum chain, websocket and node. See example below,

![](/assets/img/gateway-kovan.jpg)

For more information about `ERC20 Kovan token lists` click [here](https://github.com/CoinAlpha/gateway-api/blob/master/src/assets/erc20_tokens_kovan.json).

File location `gateway-api/src/assets/ecr20_tokens_kovan.json`

```
  {
  "name": "kovan",
  "tokens": [
    {
      "symbol": "COIN1",
      "address": "0x809F5A762e7b0CC75C42cd76098b85CB7BD2BA64",
      "decimals": 18,
      "chainId": 42
    },
    {
      "symbol": "COIN2",
      "address": "0x9866c4043bc6cf47eaf845c56f6ab221c204e0df",
      "decimals": 8,
      "chainId": 42
    },
    {
      "symbol": "COIN3",
      "address": "0x3D2097889B97A9eF23B3eA8FC10c626fbda29099",
      "decimals": 18,
      "chainId": 42
    }
  ]
}
```

Relaunch your Hummingbot client and setup an AMM_Arbitrage strategy.