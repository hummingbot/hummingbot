# Unit Testing

Create a new environment called `MOCK_API_ENABLED` that switches between normal unit tests and mock tests.

```bash
export MOCK_API_ENABLED=true
```

Before running the tests, make sure `conda` environment is enabled.

```bash
conda activate hummingbot
```

Run nosetests from `hummingbot/test/integration` directory and add `-v` for logging to see what the tests are doing and what errors come up.

```bash
nosetests -v test_binance_market.py
```

Markets that currently can run unit mock testing:

- Binance
- Coinbase Pro
- Huobi
- Liquid
- Bittrex
- KuCoin