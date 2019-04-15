# Setting up your Ethereum wallet

## Why does Hummingbot need my Ethereum wallet private key?

Strategies that transact on decentralized exchanges (such as [Radar Relay](/connectors/radar-relay) and [DDEX](/connectors/ddex)) directly interact with smart contracts on the Ethereum blockchain. Therefore, transactions must be signed and authorized, which requires your private key.

## Creating your wallet

After you start Hummingbot and run the `config` process, you are asked: *Would you like to import an existing wallet or create a new wallet?*

Respond with `create` to create a new wallet. Note that you will need to send ETH and tokens to this wallet address in order to run trading bots.

Afterwards, you are prompted to enter a password that protects the wallet. Each time you launch `hummingbot`, you need to unlock the wallet using this password in order to start running trading bots on decentralized exchanges.

## Importing your wallet

There are two ways to import your Hummingbot wallet from other wallets like Metamask and MyCrypto:

1. Importing the wallet's keyfile (recommended)
2. Importing the wallet's private key

!!! warning
    We recommend using the keyfile method over copying and pasting the private key. if your private key remains in your clipboard, there is a risk that a malicious website that you visit may utilize Javascript to access your clipboard and copy its contents.

### Keyfile (recommended)


To import your wallet using its JSON keyfile:

1. Export the JSON keyfile from other wallets such as Metamask, MyCrypto, or MyEtherWallet
2. Save the file in the `/conf` directory
3. Rename the file to `key_file_[address].json`, where `[address]` is the public Ethereum address in the format `0xabc...def`.
4. Start Hummingbot
5. Respond `import` to the question: *Would you like to import an existing wallet or create a new wallet?*
6. Your wallet should be available in the list of options.

### Private key

1. After you start Hummingbot and run the `config` process, you are asked: *Would you like to import an existing wallet or create a new wallet?*
2. Respond with `import` and you are prompted to enter the private key associated with the wallet
3. Secure your wallet with a password

## Exporting your wallet

There are two ways to export your Hummingbot wallet to other wallets like Metamask and MyCrypto:

1. Exporting the wallet's keyfile (recommended)
2. Exporting the wallet's private key

!!! warning
    We recommend using the keyfile method over copying and pasting the private key. if your private key remains in your clipboard, there is a risk that a malicious website that you visit may utilize Javascript to access your clipboard and copy its contents.

### Keyfile (recommended)

When you import or create a wallet with Hummingbot, a JSON file named `key_file_[address].json` is created in the `/conf` directory. This JSON keyfile contains the encrypted private key of your wallet and can be imported into other dApps.

### Private key

Within the `hummingbot` CLI, you can use the `export_private_key` command to display the private key associated with a wallet address. You can import your wallet to dApps like Metamask and MyCrypto using this private key as well.

