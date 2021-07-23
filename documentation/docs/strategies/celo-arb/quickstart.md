# Quickstart Guide for `celo-arb`

We have created this guide to help users of the new `celo-arb` strategy install and run the strategy on a cloud instance. 

This configuration installs the Docker build of Hummingbot on AWS. Note that you can use other cloud providers besides AWS, and you can also install Hummingbot by source or binary in addition to Docker.

## 1. Set up a cloud instance on AWS

We assume that you already have an [AWS](https://aws.amazon.com/) account.

Follow the instructions at [Installation - Cloud Server Guide - AWS](/installation/cloud/#amazon-web-services) to launch an AWS instance. However, please make the following modifications to run `celo-arb`.

### Instance type

While the free `t2.micro` tier may be sufficient to run `celo-arb`, we recommend a `t2.medium` instance as the minimum instance type for improved performance.

### Storage
By default, AWS instances come with 8 GB of storage. We recommend that you increase storage to at least 16 GB to install the Docker version along with the Celo node.

## 2. Install Docker

```bash tab="Option 1: Easy Install"
# 1) Download Docker install script
wget https://raw.githubusercontent.com/CoinAlpha/hummingbot/development/installation/install-docker/install-docker-ubuntu.sh

# 2) Enable script permissions
chmod a+x install-docker-ubuntu.sh

# 3) Run installation
./install-docker-ubuntu.sh
```

```bash tab="Option 2: Manual Installation"
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

Follow the [Celo documentation](https://docs.celo.org/getting-started/mainnet/running-a-full-node-in-mainnet) to pull the Celo Docker image and install/configure a node, but stop right after the step *Configure the node* and before the step *Start the node*:

Instead, run the following command to start an **ultra-light node** rather than a full node:
```
docker run --name celo-ultralight-node -d --restart unless-stopped -p 127.0.0.1:8545:8545 -v $PWD:/root/.celo $CELO_IMAGE --verbosity 3 --networkid $NETWORK_ID --syncmode lightest --rpc --rpcaddr 0.0.0.0 --rpcapi eth,net,web3,debug,admin,personal --etherbase $CELO_ACCOUNT_ADDRESS --bootnodes $BOOTNODE_ENODES --allow-insecure-unlock
```

**Make sure that you save the address and password of the new Celo account address you created. You will need it later.** 

## 4. Install and run Hummingbot

Install the Docker version of Hummingbot:

```bash tab="Option 1: Easy Install"
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

```bash tab="Option 2: Manual Installation"
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