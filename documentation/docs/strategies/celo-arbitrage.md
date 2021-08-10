# Celo Arbitrage

**Updated as of v0.28.1**

!!! warning
    The Celo Arbitrage Strategy could not be used on Binary Installers since it would need a [gateway](https://docs.hummingbot.io/gateway/installation/#what-is-hummingbot-gateway) connection for it to work. It can only be used when running Hummingbot from source or with Docker.

## Prerequisites

Since Celo is a blockchain protocol, in addition to the normal inventory requirements, you will need access to a Celo node and the `celo-cli` command line tool in the same machine in which you are running the Hummingbot client.

### Inventory of CELO or cUSD

1. Similar to the **arbitrage** strategy, you will need to hold inventory of Celo tokens (i.e. Celo Gold (CELO) or cUSD) in a Celo wallet and on a **secondary** exchange), in order to be able to trade and capture price differentials (i.e. buy low on one exchange, sell high on the other).
2. You may also need some CELO tokens in your Celo wallet in order to pay for transaction fees on the Celo blockchain.

### Access to a Celo node

Celo nodes allow the Hummingbot client to interact with the Celo blockchain by connecting to peers, sending transactions, and fetching chain state. Since the client just needs access to the chain and recent blocks, you can run either a Celo full node or an ultra-light node.

Follow the [Celo documentation](https://docs.celo.org/getting-started/mainnet/running-a-full-node-in-mainnet) to install and run a full node. Note that the node must be synced in order for the `celo-arb` strategy to run.

!!! tip
    Ultra-light sync mode — The `celo-arb` strategy works with Celo node running in 'ultra-light' mode, which is much faster to sync. See our [Quickstart](https://hummingbot.io/academy/celo-arb/) for instructions on how to start a node in ultra-light mode.

### `celo-cli` CLI tool

To interact with the Celo node, the Hummingbot client depends upon the `celo-cli` command line tool. Please install `celo-cli` by following these instructions in the Celo documentation.

## Setup

This configuration installs the Docker build of Hummingbot on AWS. Note that you can use other cloud providers besides AWS, and you can also install Hummingbot by source or binary in addition to Docker.

## 1. Set up a cloud instance on AWS

We assume that you already have an [AWS](https://aws.amazon.com/) account.

### Instance type

While the free `t2.micro` tier may be sufficient to run `celo-arb`, we recommend a `t2.medium` instance as the minimum instance type for improved performance.

### Storage

By default, AWS instances come with 8 GB of storage. We recommend that you increase storage to at least 16 GB to install the Docker version along with the Celo node.

## 2. Install via Docker

### Scripts

```Scripts
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-docker-ubuntu.sh

# 3) Run installation
./install-docker-ubuntu.sh
```

### Manual

```Manual
# 1) Update Ubuntu's database of software
sudo apt-get update

# 2) Install tmux
sudo apt-get install -y tmux

# 3) Install Docker
sudo apt install -y docker.io

# 4) Start and Automate Docker
sudo systemctl start docker && sudo systemctl enable docker

# 5) Change permissions for docker (optional)
# Allow docker commands without requiring sudo prefix
sudo usermod -a -G docker $USER

# 6) Close terminal
exit
```

You may need to exit and reconnect to your AWS instance afterwards.

## 3. Run a Celo ultra-light node

Follow the [Celo documentation](https://docs.celo.org/getting-started/mainnet/running-a-full-node-in-mainnet) to pull the Celo Docker image and install/configure a node, but stop before the step **Start the node**

### Mainnet

```
# Setup the environment variables required for Mainnet
export CELO_IMAGE=us.gcr.io/celo-org/geth:mainnet

# Pull Celo Docker image
docker pull $CELO_IMAGE

# Set up a data directory
mkdir celo-data-dir
cd celo-data-dir

# Create an account and address
docker run -v $PWD:/root/.celo --rm -it $CELO_IMAGE account new

# Save the address and passphrase. Use the address on environment variable.
export CELO_ACCOUNT_ADDRESS=<YOUR-ACCOUNT-ADDRESS>


```
!!! note
    Make sure that you save the address and password of the new Celo account address you created. You will need it later.

Instead, run the following command to start an **ultra-light node** rather than a full node:

```
docker run --name mainnet -d --restart unless-stopped -p 127.0.0.1:8545:8545 -v $PWD:/root/.celo $CELO_IMAGE --verbosity 3 --syncmode lightest --rpc --rpcaddr 0.0.0.0 --rpcapi eth,net,web3,debug,admin,personal --etherbase $CELO_ACCOUNT_ADDRESS --allow-insecure-unlock --nousb
```

## 4. Install and run Hummingbot

Install the Docker version of Hummingbot:

### Scripts

```Scripts
# 1) Download Hummingbot install, start, and update script
cd ~
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/create.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/start.sh
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/docker-commands/update.sh

# 2) Enable script permissions
chmod a+x *.sh

# 3) Create a hummingbot instance
./create.sh
```

### Manual

```Manual
# 1) Create folder for your new instance
cd ~
mkdir hummingbot_files

# 2) Create folders for logs, config files and database file
mkdir hummingbot_files/hummingbot_conf
mkdir hummingbot_files/hummingbot_logs
mkdir hummingbot_files/hummingbot_data

# 3) Launch a new instance of hummingbot
docker run -it \
--network host \
--name hummingbot-instance \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_conf,destination=/conf/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_logs,destination=/logs/" \
--mount "type=bind,source=$(pwd)/hummingbot_files/hummingbot_data,destination=/data/" \
coinalpha/hummingbot:latest
```

Afterwards, Hummingbot will start automatically and prompt you to set a password. After you exit, you can use the `./start.sh` and `./update.sh` commands to run and update Hummingbot, respectively.

## 5. Connect to the Celo blockchain

Run the command `connect celo`

Enter the Celo address and password from when you created the Celo account in Step 3.

You should now be connected to Celo. To check, run the `balance` command and check that the balances of CELo and cUSD match what you hold in your Celo wallet.

## Configuration parameters

The following walks through all the steps when running `create` command. These parameters are fields in Hummingbot configuration files (located in the `/conf` folder, e.g. `conf/celo_arb_[#].yml`).

### `secondary_market`

Enter another exchange you would like to trade on.

** Prompt: **

```json
Enter your secondary exchange name
>>>
```

### `secondary_market_trading_pair`

Enter the token trading pair for the secondary exchange.

** Prompt: **

```json
Enter the token trading pair you would like to trade on [secondary_market]
>>>
```

### `min_profitability`

Minimum profitability target required to execute trades.

** Prompt: **

```json
What is the minimum profitability for you to make a trade?
>>>
```

### `order_amount`

Order amount for each leg of the arbitrage trade.

** Prompt: **

```json
What is the amount of [base_asset] per order?
>>>
```

### `celo_slippage_buffer`

Percent buffer added to the Celo exchange price to account for price movement before trade execution

** Prompt: **

```json
How much buffer do you want to add to the Celo price to account for slippage (Enter 1 for 1%)?
>>> 1
```
