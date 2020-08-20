# Setting up your Ethereum wallet

## Why does Hummingbot need my Ethereum wallet private key?

Strategies that transact on decentralized exchanges (such as [Radar Relay](/connectors/radar-relay), [Bamboo Relay](/connectors/bamboo-relay), and [Dolomite](/connectors/dolomite)) directly interact with smart contracts on the Ethereum blockchain. Therefore, transactions must be signed and authorized, which requires your private key.

Run command `connect ethereum` to connect your Ethereum wallet with Hummingbot.

```
Enter your wallet private key >>>
```

## Importing your wallet

There are two ways to import your Hummingbot wallet from other wallets like Metamask and MyCrypto:

1. Importing the wallet's keyfile (recommended)
2. Importing the wallet's private key

We recommend using the keyfile method over copying and pasting the private key. If your private key remains in your clipboard, there is a risk that a malicious website that you visit may utilize Javascript to access your clipboard and copy its contents.

!!! tip "Metamask wallet"
    Using a wallet that is available in your Metamask (i.e. importing a wallet from Metamask) allows you to view orders created and trades filled by Hummingbot on the decentralized exchange's website.


### Keyfile (recommended)

To import your wallet using its JSON keyfile:

1. Export the JSON keyfile from other wallets such as Metamask, MyCrypto, or MyEtherWallet
2. Save the file in the `/conf` directory
3. Rename the file to `key_file_[address].json`, where `[address]` is the public Ethereum address in the format `0xabc...def`.
4. Start Hummingbot
5. Run `connect` command to confirm if keys are confirmed and added for ethereum.

### Private key

1. In the Hummingbot client run command `connect ethereum`
2. Ether the private key associated with the wallet

### Keyfile (recommended)

When you import a wallet with Hummingbot, a JSON file named `key_file_[address].json` is created in the `/conf` directory. This JSON keyfile contains the encrypted private key of your wallet and can be imported into other dApps.

### Private key

Within the Hummingbot CLI, you can use the `export_private_key` command to display the private key associated with a wallet address. You can import your wallet to dApps like Metamask and MyCrypto using this private key as well.