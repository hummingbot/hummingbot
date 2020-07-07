**Hummingbot is an open-source project that integrates cryptocurrency trading on both centralized exchanges and decentralized protocols. Using Hummingbot, users can run a client that executes customized, automated trading strategies for cryptocurrencies.**

## NOTES

This is a modified edition of [Hummingbot](https://hummingbot.io/) which includes a gateway for connecting to [Loopring Exchange](https://loopring.io), a decentralized exchange (DEX) built on the open source [Loopring Protocol](https://loopring.org). Loopring.io is a high performance non-custodial Ethereum exchange, allowing for trading with high throughput, low settlement cost, and is the world’s first DEX powered by zk-rollup technology. 

The Loopring gateway was contributed by, and is actively developed and maintained by [Linq](https://linq.network/), an institutional digital asset liquidity provider, and supporters of Loopring’s architecture. 

Linq has partnered with Loopring to release this edition of Hummingbot to support and grow the community able to programmatically trade on [Loopring.io](https://loopring.io/). Loopring offers periodic [liquidity mining campaigns](https://medium.com/loopring-protocol/loopring-exchange-liquidity-mining-competition-748917b277e6) whereby traders are rewarded for adding liquidity (resting limit orders) to certain trading pairs on Loopring. Using this edition of Hummingbot, almost anyone can learn to participate in adding liquidity to the exchange and earn compensation incentives.

To set up this software, follow the instructions in the RUNNING section below.

HAPPY LIQUIDITY MINING!

## RUNNING

1. The code can be built to a docker container from the project folder by running: 
`docker build --pull --rm -f "Dockerfile" -t loopring:latest "."`

2. Launch bash on the built image: 
`docker run -it loopring:latest bash`

3. Run hummingbot with the loopring connector by then running this command inside the container: 
`/opt/conda/envs/hummingbot/bin/python3 bin/hummingbot_quickstart.py`

4. You can use the loopring connector by then running the following hummingbot command: 
`connect loopring` 
and then entering the requested information from a loopring account

5. Create and run the pure_market_making strategy, or any other available strategy, and specify your parameters.

## REFERENCES

For detailed Hummingbot help, please refer to Hummingbot project homepage [https://github.com/CoinAlpha/hummingbot](https://github.com/CoinAlpha/hummingbot).

To begin, first create a Loopring DEX account at https://loopring.io/ with your Ethereum wallet. Copy your exchange credentials listed under “Export Account”, and insert them into Hummingbot to connect your account and begin automated trading. For a comprehensive description of these keys and Loopring DEX API, please refer to [https://docs.loopring.io/en/](https://docs.loopring.io/en/).

## CONTACT US
For further information about this forked version of Hummingbot, and Loopring specific functionality, please contact Linq or Loopring below: 
* [exchange@loopring.io](mailto:exchange@loopring.io)
* [Loopring Discord](https://discord.gg/KkYccYp)
* [corporate@linq.network](mailto:corporate@linq.network)
