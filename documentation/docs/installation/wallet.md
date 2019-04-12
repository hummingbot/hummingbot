# Setting up your Ethereum wallet

## Why does Hummingbot need my Ethereum wallet private key?

Strategies that transact on decentralized exchanges (such as [Radar Relay](/connectors/radar-relay) and [DDEX](/connectors/ddex)) are direct interactions with that exchange’s smart contracts on the Ethereum blockchain.  Therefore, transactions must be signed and authorized, which requires your private key.

## Importing and creating your wallet

During the `config` process, users are asked: *Would you like to import an existing wallet or create a new wallet?* 

To import a new wallet, you need to import the private key associated with the wallet.

Afterwards, you are prompted to enter a password that protects the wallet. Each time you launch `hummingbot`, you need to unlock the wallet using this password in order to start running trading bots on decentralized exchanges.

## Exporting your wallet

There are two ways to export your Hummingbot wallet to dApps like Metamask and MyCrypto:

1. Exporting the wallet's keyfile (recommended)
2. Exporting the wallet's private key

### Keyfile (recommended)

When you import or create a wallet with Hummingbot, a file named `key_file_*.json` is created in the `/conf` directory. This JSON keyfile contains the encrypted private key of your wallet and can be imported into other dApps.

### Private key

Within the `hummingbot` CLI, you can use the `export_private_key` command to display the private key associated with a wallet address. You can import your wallet to dApps like Metamask and MyCrypto using this private key as well.

!!! warning
    We recommend using the keyfile method over copying and pasting the private key. if your private key remains in your clipboard, there is a risk that a malicious website that you visit may utilize Javascript to access your clipboard and copy its contents.
