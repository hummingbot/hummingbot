## What is Hummingbot Gateway?

Hummingbot Gateway is a API server that allows Hummingbot to connect to [protocols](/protocol-connectors/overview/) that are used in the [amm-arb strategy](/strategies/amm-arb/) and other future strategies. This is a light web server that enables Hummingbot client to send and receive data from different blockchain protocols and provides an easier entry point for external devs to build connectors to other protocols.

!!! note
    To use Gateway, you need to install Hummingbot using Docker or from source.

## Create SSL certificates

1. Run the command `generate_certs` in the Hummingbot client
2. Enter a passphrase to be used later during installation

![](/assets/img/generate-certs.gif)

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
    When creating a Gateway instance for Ethereum protocol connectors such as [Balancer](/connectors/balancer), [Uniswap](/connectors/uniswap), and [Perpetual Finance](/protocol-connectors/perp-fi) the script picks up the settings from your global config file (`conf_global.yml`). Make sure to connect them first from the Hummingbot client before installing Gateway.

By default, Gateway will install on port `5000` which Hummingbot will connect to. If the default port is not available, Gateway will find the next port number.

4. The file `gateway.env` is created where your Gateway settings are saved.

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

- Tested versions `v10.22.0, v10.22.1 and v10.23.1`.

```bash
# to check your current version
node -v
```

![](/assets/img/gw_version.gif)

!!! tip
    You can install [nvm] to manage and use different node versions on the same system.

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
yarn install
```

![](/assets/img/gw_yarn.gif)

```bash
# copy sample environment
cp .env.example .env
```

![](/assets/img/gw_env.gif)

- Edit `.env` file with your favorite text editor then save changes.
- There are 3 ways to start the gateway

```bash
# run dev mode with hot reload on code changes
yarn run dev
```

```bash
# run debug mode with additional route debug logging
yarn run debug
```

```bash
# run prod mode
yarn run start
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

Add the following to your `erc20_tokens_override.json` found on your Hummingbot directory under `conf` or `hummingbot_conf` folder.

```
  "BAT": "0x1f1f156E0317167c11Aa412E3d1435ea29Dc3cCE",
  "WETH": "0xd0A1E359811322d97991E03f863a0C30C2cF029C",
  "DAI": "0x1528F3FCc26d13F7079325Fb78D9442607781c8C",
  "MKR": "0xef13C0c8abcaf5767160018d268f9697aE4f5375",
  "USDC": "0x2F375e94FC336Cdec2Dc0cCB5277FE59CBf1cAe5",
  "REP": "0x8c9e6c40d3402480ACE624730524fACC5482798c",
  "WBTC": "0xe0C9275E44Ea80eF17579d33c55136b7DA269aEb",
  "SNX": "0x86436BcE20258a6DcfE48C9512d4d49A30C4d8c4",
  "ANT": "0x37f03a12241E9FD3658ad6777d289c3fb8512Bc9",
  "ZRX": "0xccb0F4Cf5D3F97f4a55bb5f5cA321C3ED033f244"
```

Relaunch your Hummingbot client and setup an AMM_Arbitrage strategy.
