# Unit Testing

Add -v to nosetests for logging to see what the tests are doing and what errors come up.

```bash
nosetests -v test_coinbase_pro_market.py
```

Make sure to create ENV vars found [here](https://github.com/CoinAlpha/hummingbot/blob/c71bc06cbcd7c346c09ac8868e802558f114bbf1/conf/__init__.py#L42) for the keys. For example, run this before running the Coinbase Pro market test.

```
export COINBASE_PRO_API_KEY=<INSERT>
export COINBASE_PRO_SECRET_KEY=<INSERT>
export COINBASE_PRO_PASSPHRASE=<INSERT>
```

## Unit Test Requirements

Below are the requirements when running the tests for each market.

| Market | Wallet | API Key | API Secret | Token1 | Token1 Amount | Token2 | Token2 Amount | Token3 | Token3 Amount | Token4 | Token4 Amount | Token Address1 | Token Address2 | Token Address3 | Comment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance | N | Y | Y | ZRX | 80 | ETH | 0.2 | IOST | 3800 | NA | NA | NA | NA | NA | Requires 0.02 ETH worth of ZRX and IOST. Based on calculation, 0.1 ETH worth of both tokens is recommended. |
| Coinbase Pro | N | Y | Y | ETH | 0.1 | USDC | 20 | USD | 20 | NA | NA | NA | NA | NA | Requires 0.02 ETH worth of USDC and USD. Based on calculation, 0.1 ETH worth of both tokens is recommended. |
| Huobi | N | Y | Y | ETH | 0.2 | USDT | 40 | NA | NA | NA | NA | NA | NA | NA | Requires 0.1 ETH. |
| Bittrex | N | Y | Y | ETH | 0.1 | LTC | 10 | XRP | 10 | NA | NA | NA | NA | NA | Requires 10 LTC, 10 XRP and 0.1 ETH. |
| Radar Relay | Y | N | N | ETH | 0.1 | WETH | 0.2 | ZRX | 20 | NA | NA | 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 | 0xE41d2489571d322189246DaFA5ebDe1F4699F498 | 0xE41d2489571d322189246DaFA5ebDe1F4699F498 | Requires 10 ZRX, 0.05 ETH and 0.1 WETH. |
| Bamboo Relay | Y | N | N | WETH | 0.1 | DAI | 20 | NA | NA | NA | NA | 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 | 0x89d24A6b4CcB1B6fAA2625fE562bDD9a23260359 | 0xE41d2489571d322189246DaFA5ebDe1F4699F498 | Requires 0.1 WETH and 20 DAI. |
