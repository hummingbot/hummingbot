# Developing a Connector for a New Blockchain

!!! warning
    This document is inocmplete and a work in progress.

Hummingbot currently has connectors to Ethereum-based exchanges and has built in [Ethereum wallet support](https://github.com/CoinAlpha/hummingbot/tree/master/hummingbot/wallet/ethereum).

Developing a connector for a blockchain other than Ethereum would require the creation of similar, blockchain-specific functionality:

- blockchain wallet
- token addresses
- event watchers: balances, contract events, token events
- exchange interactions
