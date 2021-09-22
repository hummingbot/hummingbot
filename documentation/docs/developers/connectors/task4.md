# Task 4 — API Throttler, Configurations & Additional Functions

This section explains the configuration for the required file, functions, and other optional settings to integrate your connector with Hummingbot.

## API Throttler

This section will detail the necessary steps to integrate the `AsyncThrottler` into the connector. 
The `AsyncThrottler` class utilizes asynchrounous context managers to throttle API and/or WebSocket requests.

!!! note
    The integration of the `AsyncThrottler` into the connector is entirely optional, but it is recommended to allow users to manually configure the usable rate limits per Hummingbot client.

### Types of Rate Limits

There are several types of rate limits that can be handled by the `AsyncThrottler` class. The following sections will detail(with examples) how to initialize the necessary `RateLimit` and how to the throttler is consumed by the connector for each of the different rate limit types. 

!!! warning
    It is important to identify the exchange's rate limit implementation.

#### 1. Rate Limit per endpoint

This refers to rate limits that are applied on a per endpoint basis. For this rate limit type, each endpoint would be assigned a limit and time interval. 

!!! note
    Examples of existing connectors that utilizes this rate limit implementation are:</br>
      (1) Kucoin</br>
      (2) Crypto.com</br>

#### 2. Rate Limit Pools

Rate limit pools refer to a group of endpoints that consumes from a single rate limit. An example of this can be seen in the AscendEx connector.

!!! note
    Examples of existing connectors that utilizes this rate limit implementation are:</br>
      (1) AscendEx</br>
      (2) Binance, Binance Perpetual</br>
      (3) Gate.io</br>
      (4) Ndax</br>
      (5) Bybit Perpetual</br>

#### 3. Weighted Rate Limits

For weighted rate limits, each endpoint is assigned a request weight. Generally, these exchange would utilize Rate Limit Pools in conjunction with the request weights. 

!!! note
    Examples of existing connectors that utilizes this rate limit implementation are:</br>
      (1) Binance, Binance Perpetual</br>

### Configuring and Consuming Rate Limits

Below details how to configure and consume the rate limits for each respective rate limit types.

#### 1. Rate Limit per endpoint

1. Configuring Rate Limits

We will be using the Crypto.com connector as an example.

!!! note
    Rate Limits for Crypto.com can be found [here](https://exchange-docs.crypto.com/spot/index.html#rate-limits).

All the rate limits are to be initialized in the `crypto_constants.py` file.

```python
RATE_LIMITS = [
    RateLimit(limit_id=CHECK_NETWORK_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=GET_TRADING_RULES_PATH_URL, limit=100, time_interval=1),
    RateLimit(limit_id=CREATE_ORDER_PATH_URL, limit=15, time_interval=0.1),
    RateLimit(limit_id=CANCEL_ORDER_PATH_URL, limit=15, time_interval=0.1),
    RateLimit(limit_id=GET_ACCOUNT_SUMMARY_PATH_URL, limit=3, time_interval=0.1),
    RateLimit(limit_id=GET_ORDER_DETAIL_PATH_URL, limit=30, time_interval=0.1),
    RateLimit(limit_id=GET_OPEN_ORDERS_PATH_URL, limit=3, time_interval=0.1),
]
```

!!! note
    `time_interval` here is in seconds. i.e. The rate limits for `CREATE_ORDER_PATH_URL` is 15 requests every 100ms

2. Consuming Rate Limits

#### 2. Rate Limit Pools


#### 3. Weighted Rate Limits

### Consuming AsyncThrottler

The throttler should be consumed by all relevant classes that issues an API endpoints. Namely the `Exchange/Derivative`, `APIOrderBookDataSource` and `UserStreamDataSource` classes.

In this example, we will use referencing the `CryptoComExchange` class.

In the ```__init__()``` function, we have to initialize the `AsyncThrottler`
```python
from hummingbot.connector.exchange.crypto_com import crypto_com_constants as CONSTANTS

class CryptoComExchange(ExchangeBase):
  def __init__(...):
    ...
    self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
```

To consume the throttler when executing an API request, we simple wrap the contents of the `_api_request(...)` function in an asynchrounous context manager as seen below.

```python
def _api_request(...):
  async with self._throttler.execute_task(path_url):
    ...
```
## Configuration

In `setup.py`, include the new connector package into the `packages` list as shown:

```python
packages = [
   "hummingbot",
   .
   .
   "hummingbot.connector.exchange.xyz",
   "hummingbot.connector.exchange.[new_connector]",
]
```

In `hummingbot/templates/conf_global_TEMPLATE.yml`, add entries with `null` value for each key in your utils KEYS.
  You will also need to increment `template_version` by one. For example:

```python
template_version: [+1]

[new_connector]_api_key: null
[new_connector]_secret_key: null
```

In `hummingbot/templates/conf_fee_overrides_TEMPLATE.yml`, add maker and taker fee entries (use fee_amount when your FEE_TYPE is FlatFee).
  You will also need to increment `template_version` by one. For example:

```python
template_version: [+1]

[new_connector]_maker_fee:
[new_connector]_taker_fee:
```

## Additional Utility Functions

### (Optional) Add members for Ethereum type connector

| Member                           | Type   | Description                                                                                                                     |
| -------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `USE_ETHEREUM_WALLET`            | `bool` | `True` if connector requires user's Ethereum wallet, which the user can set it up using `connect` command.                      |
| `FEE_TYPE`                       | `str`  | Set this to FlatFee if the trading fee is fixed flat fee per transaction, the `DEFAULT_FEES` will then be in the flat fee unit. |
| `FEE_TOKEN`                      | `str`  | Token name in FlatFee fee type, i.e. `ETH`.                                                                                     |

### (Optional) Add other API domains

This is only relevant if:

- Exchange supports different domains by changing API URLs domains, i.e. `binance.com` & `binance.us` or `probit.com` & `probit.kr`
- Exchange supports a `testnet` environment.

| Member                           | Type                              | Description                                                                                                                                                      |
| -------------------------------- | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OTHER_DOMAINS`                  | `List[str]`                       | A list of other domain connector names, will appear to users as new connectors they can choose.                                                                  |
| `OTHER_DOMAINS_PARAMETER`        | `Dict[str, str]`                  | A dictionary of additional `domain` parameter for each `OTHER_DOMAIN`, this parameter (string) is passed in during connector, and order book tracker `__init__`. |
| `OTHER_DOMAINS_EXAMPLE_PAIR`     | `Dict[str, str]`                  | An example of a supported trading pair for each domain.                                                                                                          |
| `OTHER_DOMAINS_DEFAULT_FEES`     | `Dict[str, List[Decimal]]`        | A dictionary of default trading fees \[maker fee and taker fee] for each domain.                                                                                 |
| `OTHER_DOMAINS_KEYS`             | `Dict[str, Dict[str, ConfigVar]]` | A dictionary of required keys for each domain.                                                                                                                   |

!!! warning
    If domain settings are used, ensure your connector uses the `domain` parameter to update base API URLs and set the exchange name correctly. Refer to `Binance` connector on how to achieve this.
