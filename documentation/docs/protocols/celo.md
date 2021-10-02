## `celo-cli` tool

To interact with the Celo node, the Hummingbot client depends upon the `celo-cli` command line tool. Please install `celo-cli` by following [these instructions](https://docs.celo.org/command-line-interface/introduction) in the Celo documentation.

## Connect to wallet

Run `connect celo` in Hummingbot.

## Connect ultra-light node

Celo nodes allow the Hummingbot client to interact with the Celo blockchain by connecting to peers, sending transactions, and fetching chain state. Since the client just needs access to the chain and recent blocks, you can run either a Celo full node or an ultra-light node.

Follow the [Celo documentation](https://docs.celo.org/getting-started/mainnet/running-a-full-node-in-mainnet) to pull the Celo Docker image and install/configure a node, but stop before the step **Start the node**:

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

Instead of installing a full node, run the following command to start an **ultra-light node**:

```
docker run --name mainnet -d --restart unless-stopped -p 127.0.0.1:8545:8545 -v $PWD:/root/.celo $CELO_IMAGE --verbosity 3 --syncmode lightest --rpc --rpcaddr 0.0.0.0 --rpcapi eth,net,web3,debug,admin,personal --etherbase $CELO_ACCOUNT_ADDRESS --allow-insecure-unlock --nousb
```

## Guide

See the [Celo-Arb Quickstart guide](https://hummingbot.io/academy/celo-arb/)
