# Connecting to Exchange

## Requirements

Private keys and API keys are stored locally for the operation of the Hummingbot client only. At no point will private or API keys be shared to CoinAlpha or be used in any way other than to authorize transactions required for the operation of Hummingbot.

### API keys

When trading on a centralized exchange, you will need to connect Hummingbot and the exchange using API keys. These are account-specific credentials that allow access to live information and trading outside of the exchange website. Follow the instructions specific to your exchange on how to create API keys.

Example:

- [How to create Binance API key](https://www.binance.com/en/support/faq/360002502072)
- [How to create KuCoin API key](https://support.kucoin.plus/hc/en-us/articles/360015102174-How-to-Create-an-API)
- [How to create Coinbase Pro API key](https://help.coinbase.com/en/pro/other-topics/api/how-do-i-create-an-api-key-for-coinbase-pro)

!!! warning
      We recommend using only **read + trade** enabled API keys. It is not necessary to enable **withdraw**, **transfer**, or anything equivalent to retrieving assets from your wallet.

## Wallets

### Create a wallet in MetaMask.io

![metamask](/assets/img/metamask.png)

One of the reliable wallets that traders can use is a MetaMask Wallet. Metamask.io is a browser extension that lets you access Ethereum's Dapp ecosystem. The access provides you a wallet with private keys and passphrase that can store tokens in a specific network.
(i.e Ethereum Mainnet, Ropsten Test Network, Kovan Test Network)

!!! note
      Secure the password, private key, and passphrase of your wallet as this can no longer be accessed or changed once forgotten. It is a best practice to secure a cold wallet/offline version of the private keys.

You can also use other alternatives of Metamask.io wallet. List of alternative wallets can be found [here](https://themoneymongers.com/best-erc20-token-wallets/).

### Wallet private keys

Strategies that transact on decentralized exchanges and protocols directly interact with smart contracts on the Ethereum blockchain. Therefore, transactions must be signed and authorized, which requires your private key. Check with your wallet provider on how to export private keys.

Example:

- [MetaMask - How to Export an Account Private Key](https://metamask.zendesk.com/hc/en-us/articles/360015289632-How-to-Export-an-Account-Private-Key)

## Setup Ethereum wallet

### Why does Hummingbot need my Ethereum wallet private key?

Strategies that transact on decentralized exchanges (such as [Radar Relay](/spot-connectors/radar-relay), [Bamboo Relay](/spot-connectors/bamboo-relay), and [Dolomite](/spot-connectors/dolomite)) directly interact with smart contracts on the Ethereum blockchain. Therefore, transactions must be signed and authorized, which requires your private key.

Run command `connect ethereum` to connect your Ethereum wallet with Hummingbot.

```
Enter your wallet private key >>>
```

### Importing your wallet

There are two ways to import your Hummingbot wallet from other wallets like Metamask and MyCrypto:

1. Importing the wallet's keyfile (recommended)
2. Importing the wallet's private key

We recommend using the keyfile method over copying and pasting the private key. If your private key remains in your clipboard, there is a risk that a malicious website that you visit may utilize Javascript to access your clipboard and copy its contents.

!!! tip
      For Metamask wallet, using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.

#### Keyfile (recommended)

To import your wallet using its JSON keyfile:

1. Export the JSON keyfile from other wallets such as Metamask, MyCrypto, or MyEtherWallet
2. Save the file in the `/conf` directory
3. Rename the file to `key_file_[address].json`, where `[address]` is the public Ethereum address in the format `0xabc...def`.
4. Start Hummingbot
5. Run `connect` command to confirm if keys are confirmed and added for ethereum.

#### Private key

1. In the Hummingbot client run command `connect ethereum`
2. Enter the private key associated with the wallet

#### Keyfile (recommended)

When you import a wallet with Hummingbot, a JSON file named `key_file_[address].json` is created in the `/conf` directory. This JSON keyfile contains the encrypted private key of your wallet and can be imported into other dApps.

#### Private key

Within the Hummingbot CLI, you can use the `export_private_key` command to display the private key associated with a wallet address. You can import your wallet to dApps like Metamask and MyCrypto using this private key as well.

### Export Keys

### `export keys`

Displays API keys, secret keys and wallet private key in the command output pane.

```
>>>  export keys

Enter your password >>> *****

Warning: Never disclose API keys or private keys. Anyone with your keys can steal any assets held in your account.

API keys:
binance_api_key:
binance_api_secret:

Ethereum wallets:
Public address:
Private key:

```

### `export trades`

Exports all trades in the current session to a .csv file.

```
>>>  export trades

Enter a new csv file name >>> trade_list
Successfully exported trades to logs/trade_list.csv

```

## Setup Ethereum nodes

You need an Ethereum node for strategies that trade on Ethereum-based decentralized exchanges, such as Radar Relay, Bamboo Relay, and Dolomite.

Run command `config ethereum_rpc_url` to use your Ethereum node with Hummingbot.

```
Which Ethereum node would you like your client to connect to? >>>
```

Below, we list different ways that you can access an Ethereum node.

### Option 1. Infura

[Infura](https://infura.io/) provides free and the most widely used Ethereum nodes.

1. Sign up for an account on infura.io
   ![infura](/assets/img/infura1.png)
2. Click on **Ethereum** and **Create a project**.
   ![infura2](/assets/img/infura2.png)
3. Name your project and click **Create**.
4. In **Keys** section and under **Endpoints** you'll find your Ethereum node as shown in the highlighted area.
   ![infura3](/assets/img/infura3.png)
5. The websocket address is below the Ethereum node that starts with `wss://`

### Option 2. Run your own local node

The most decentralized way to access an Ethereum node is to run your own node!

Running your own node may require dedicated storage and compute, as well as some technical skills. These are the two most widely used Ethereum clients:

- [Geth (go-ethereum)](https://github.com/ethereum/go-ethereum/wiki/Building-Ethereum)
- [Parity](https://github.com/paritytech/parity-ethereum)

!!! note
      These may require several hours to days to sync and may require some troubleshooting when first running.


### Option 3. Dedicated blockchain hardware

Get dedicated hardware for your Ethereum node. Ethereum nodes are meant to run constantly 24/7 and use up a material amount of computational resources (CPU, RAM, and storage). For more serious users, it may make sense to use dedicated hardware.

#### Software

- [DAppNode](https://dappnode.io/) is software that automates the installation and operation of Ethereum (as well as other blockchains) on dedicated hardware. It is easier to start and operate an Ethereum node and can run other blockchains.

#### Hardware

- [IntelⓇ NUC mini PC](https://www.intel.com/content/www/us/en/products/boards-kits/nuc.html): DIY, customize and configure your own hardware.
- [Avado](https://ava.do/): purpose built hardware that is pre-loaded with DAppNode.

## Advanced database configuration

!!! warning
      This is a recently released experimental feature. Running any trading bots without manual supervision may incur additional risks. It is imperative that you thoroughly understand and test the strategy and parameters before deploying bots that can trade in an unattended manner.

Hummingbot uses SQLite for database by default, but it may be limiting for some cases such as sharing data to external system, in some cases user may want to use their own preferred client/server RDBMS for it.

Other RDBMS are supported on Hummingbot through SQLAlchemy, it has [included some widely used RDBMS dialects](https://docs.sqlalchemy.org/en/13/dialects/index.html), i.e.:

- PostgreSQL
- MySQL
- Oracle
- Microsoft SQL Server

These dialects requires separate DBAPI driver to be installed on Hummingbot's conda environment, see [SQLAlchemy documentation](https://docs.sqlalchemy.org/en/13/dialects/index.html) for more information on appropriate DBAPI driver for each RDBMS. For example, to use PostgreSQL, `psycopg2` need to be installed. Run the following command to install it using conda:

```
conda install psycopg2
```

To configure RDBMS connection, we need to edit `conf_global.yml` in `/conf` directory.

```
- Advanced database options, currently supports SQLAlchemy's included dialects
- Reference: https://docs.sqlalchemy.org/en/13/dialects/

db_engine: sqlite
db_host: 127.0.0.1
db_port: '3306'
db_username: username
db_password: password
db_name: dbname
```

### Configuration parameters

| Configuration Parameter | Possible Values                              |
| ----------------------- | -------------------------------------------- |
| db_engine               | `sqlite`,`postgres`,`mysql`,`oracle`,`mssql` |
| db_host                 | any string e.g. `127.0.0.1`                  |
| db_port                 | any string e.g. `3306`                       |
| db_username             | any string e.g. `username`                   |
| db_password             | any string e.g. `password`                   |
| db_name                 | any string e.g. `dbname`                     |

### SQLAlchemy dialects

It is also possible to connect with available SQLAlchemy's external dialects (e.g. Amazon Redshift). But the feature is not currently supported in Hummingbot due to its various DSN format, **use this at your own risk**.

<small>Feature contribution by [Rupiah Token](https://rupiahtoken.com).</small>

### Ethereum node

An Ethereum node is required when trading on Ethereum-based decentralized exchanges or protocols. There are different ways you can access an Ethereum node.

1. [Infura](https://infura.io/) provides free and the most widely used Ethereum node. Their blog post below provides more information, including how to access:
   - [Getting started with Infura](https://blog.infura.io/getting-started-with-infura-28e41844cc89/)
1. **Running your own local node.** It may require dedicated storage and compute, as well as some technical skills. Note that these may require several hours to sync and may require some troubleshooting when first running. These are the two most widely used Ethereum clients:
   - [Geth (go-ethereum)](https://github.com/ethereum/go-ethereum/wiki/Building-Ethereum)
   - [Parity](https://github.com/paritytech/parity-ethereum)
1. **Using dedicated blockchain hardware.** Ethereum nodes are meant to constantly run 24/7 and use up a material amount of computational resources (CPU, RAM, and storage). For more serious users, it may make sense to use dedicated hardware.
   - [DAppNode](https://dappnode.io/) is software that automates the installation and operation of Ethereum (as well as other blockchains) on dedicated hardware. It is easier to start and operate an Ethereum node and can run other blockchains.
   - [IntelⓇ NUC mini PC](https://www.intel.com/content/www/us/en/products/boards-kits/nuc.html) : DIY, customize and configure your own hardware
   - [Avado](https://ava.do/) : purpose-built hardware that is pre-loaded with DAppNode

## Adding or replacing keys in Hummingbot

### Connect to exchanges

1. Run `connect [exchange_name]` command e.g., `connect binance` will prompt connection to Binance exchange
1. Enter API and secret keys when prompted
1. Other exchanges may require additional details such as account ID, exchange address, etc.

### Connect to Ethereum

Follow the instructions below to connect to decentralized exchanges or protocol running on Ethereum such as Balancer, Uniswap, and Perpetual Finance.

1. Run `connect ethereum` command
1. Enter your wallet private key
1. Enter the Ethereum node endpoint starting with https://
1. Enter the websocket address starting with wss://

## Checking connection status

Run the `connect` command to view the connection status. It also shows failed connections due to connectivity issues, invalid API key permissions, etc.

![](/assets/img/connection-status.png)

**Keys Added** column indicates if API keys are added to Hummingbot.

**Keys Confirmed** column shows the status if Hummingbot has successfully connected to the exchange or protocol.

**Connector Status** column is an indicator if there are known issues with the connector or working correctly. More info in [Spot Connector Status](/spot-connectors/overview) and [Protocol Connector Status](/protocol-connectors/overview).
