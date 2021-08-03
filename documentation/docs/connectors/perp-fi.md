# Perpetual Finance

!!! note
    This connector has undergone code review, internal testing and was shipped during one of our most recent releases. As part of User Acceptance Testing, we encourage user to report any issues with this connector to our [Discord server](https://discord.com/invite/2MN3UWg) or [submit a bug report](https://github.com/CoinAlpha/hummingbot/issues/new?assignees=&labels=bug&template=bug_report.md&title=)

Perpetual Protocol is a decentralized perpetual contract trading protocol for every asset, with a Uniswap-inspired Virtual Automated Market Makers (Virtual AMMs) and a built-in Staking Reserve, which backs and secures the Virtual AMMs.

!!! warning
    Currently, [Perpetual Finance](/protocol-connectors/perp-fi/) could not be used on Binary Installers since it would need a [gateway](https://docs.hummingbot.io/gateway/installation/#what-is-hummingbot-gateway) connection for it to work. It can only be used when running Hummingbot from source or with Docker.

## Prerequisites

- Ethereum wallet (refer to our guide [here](/operation/connect-exchange/#setup-ethereum-wallet))
- Hummingbot Gateway (done after connecting to Perpetual Finance)
- Some xDai asset in the wallet for gas
- xUSDC - all trades are funded and settled in xUSDC. You can obtain xUSDC by depositing USDC and receiving the xUSDC equivalent on the Perpetual Finance exchange [here](https://perp.exchange)

## Connecting to Perpetual Finance

When creating Hummingbot Gateway, it picks up the Ethereum settings in the global config file, which we can set up in the Hummingbot client.

1. Run the command `connect ethereum` in the Hummingbot client
2. Enter your wallet private key
3. Enter Ethereum node address (starts with https://)
4. Enter the WebSocket connection address of your Ethereum node (starts with wss://)

![](/assets/img/connect-ethereum.gif)

## Install Hummingbot Gateway

After adding your Ethereum wallet and node in Hummingbot, follow the guide in the link below on how to install Hummingbot Gateway.

- [Hummingbot Gateway Installation](/gateway/installation/)
