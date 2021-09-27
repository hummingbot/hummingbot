# Task 4 — API Throttler, Configurations & Additional Functions

This section explains the steps required to include API throttler functionality into the connector and details the necessary configurations to integrate the connector with Hummingbot.

## API Throttler

This section will detail the necessary steps to integrate the `AsyncThrottler` into the connector. 
The `AsyncThrottler` class utilizes asynchronous context managers to throttle API and/or WebSocket requests and avoid reaching the exchange's server rate limits.

!!! note
    The integration of the `AsyncThrottler` into the connector is entirely optional, but it is recommended to enable a better user experience as well as allowing users to manually configure the usable rate limits per Hummingbot instance.

### RateLimit & LinkedLimitWeightPair Data classes

The `RateLimit` data class is used to represent a rate limit defined by exchanges, while the `LinkedLimitWeightPair` data class is used to associate an endpoint consumption weight to its API Pool (defaults to 1 if it is not specified)

!!! note
    `limit_id` can be any arbitrarily assigned value. In the examples given in the next few sections, the `limit_id` assigned to the various rate limits are either a generic API pool name or the path url of the API endpoint.

```python
@dataclass
class LinkedLimitWeightPair:
    limit_id: str
    weight: int = DEFAULT_WEIGHT

class RateLimit:
    """
    Defines call rate limits typical for API endpoints.
    """

    def __init__(self,
                 limit_id: str,
                 limit: int,
                 time_interval: float,
                 weight: int = DEFAULT_WEIGHT,
                 linked_limits: Optional[List[LinkedLimitWeightPair]] = None,
                 ):
        """
        :param limit_id: A unique identifier for this RateLimit object, this is usually an API request path url
        :param limit: A total number of calls * weight permitted within time_interval period
        :param time_interval: The time interval in seconds
        :param weight: The weight (in integer) of each call. Defaults to 1
        :param linked_limits: Optional list of LinkedLimitWeightPairs. Used to associate a weight to the linked rate limit.
        """
        self.limit_id = limit_id
        self.limit = limit
        self.time_interval = time_interval
        self.weight = weight
        self.linked_limits = linked_limits or []
```



### Types of Rate Limits

There are several types of rate limits that can be handled by the `AsyncThrottler` class. The following sections will detail (with examples) how to initialize the necessary `RateLimit` and the interaction between the connector and the throttler for each of the different rate limit types. 

!!! warning
    It is important to identify the exchange's rate limit implementation.

#### 1. Rate Limit per endpoint

This refers to rate limits that are applied on a per endpoint basis. For this rate limit type, the key information to retrieve for each endpoint would be its assigned **limit** and **time interval**.
Note that the time interval is on a rolling basis. For example, if an endpoint's rate limit is 20 and the time interval is 60, this meant that the throttler will check if there are 20 calls made (to the same endpoint) within the past 60 seconds from the current moment.

!!! note
    Examples of existing connectors that utilizes this rate limit implementation are:</br>
      (1) Kucoin</br>
      (2) Crypto.com</br>

##### Configuring Rate Limits

  As mentioned above, the key information to retrieve from the exchange are the `limit` and `time_interval` (in seconds) of each endpoint. We will be referencing the Crypto.com connector as an example for exchanges that implement rate limits per endpoint.

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

#### 2. Rate Limit Pools

Rate limit pools refer to a group of endpoints that consumes from a single rate limit. For this rate limit type, the key information to retrieve for each endpoint are its assigned pool(s) and its respective limit and time interval.

!!! note
    Examples of existing connectors that utilizes this rate limit implementation are:</br>
      (1) Binance, Binance Perpetual</br>
      (2) Ndax</br>

##### Configuring Rate Limits

An example of an exchange implementing this can be seen in the Ndax connector.

Note

  All the rate limit are initialized in the `ndax_constants.py` file. 

  ```python
  # Pool IDs
  HTTP_ENDPOINTS_LIMIT_ID = "AllHTTP"
  WS_ENDPOINTS_LIMIT_ID = "AllWs"

  RATE_LIMITS = [
    # REST API Pool(applies to all REST API endpoints)
    RateLimit(limit_id=HTTP_ENDPOINTS_LIMIT_ID, limit=HTTP_LIMIT, time_interval=MINUTE),
    # WebSocket Pool(applies to all WS requests)
    RateLimit(limit_id=WS_ENDPOINTS_LIMIT_ID, limit=WS_LIMIT, time_interval=MINUTE),
    # Public REST API endpoint
    RateLimit(
        limit_id=MARKETS_URL,
        limit=HTTP_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(HTTP_ENDPOINTS_LIMIT_ID)],
    ),
    # WebSocket Auth endpoint
    RateLimit(
        limit_id=ACCOUNT_POSITION_EVENT_ENDPOINT_NAME,
        limit=WS_LIMIT,
        time_interval=MINUTE,
        linked_limits=[LinkedLimitWeightPair(WS_ENDPOINTS_LIMIT_ID)],
    ),
  ]
  ```

!!! note
    Notice that we assign an abitruary limit id (i.e. `HTTP_ENDPOINTS_LIMIT_ID`) to the API pools and we use the [`LinkedLimitWeightPair`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/api_throttler/data_types.py) to assign an endpoint to the API pool. Also do note that an endpoint may belong to multiple other endpoints. It is also worth noting that there can be more complex implementations to API pools as seen in the ByBit Perpetual connector [here](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/derivative/bybit_perpetual/bybit_perpetual_constants.py).

#### 3. Weighted Request Rate Limits

For weighted rate limits, each endpoint is assigned a request weight. Generally, these exchanges would utilize Rate Limit Pools in conjunction with the request weights, where different endpoints will have a different impact on the given pool. Key information to retrieve for these exchanges are the weights for each endpoint, limits and the time intervals for the API Pool.

!!! note
    Examples of existing connectors that utilizes this rate limit implementation are:</br>
      (1) Binance, Binance Perpetual</br>

##### Configuring Rate Limits

An example of an exchange implementing this type of rate limit can be seen in the Binance connector.

!!! note
    Rate Limits for Binance can be found in the API response for the `GET /api/v3/exchangeInfo` endpoint [here](https://binance-docs.github.io/apidocs/spot/en/#exchange-information).

```python
RATE_LIMITS = [
    # Pools
    RateLimit(limit_id=REQUEST_WEIGHT, limit=1200, time_interval=ONE_MINUTE),
    RateLimit(limit_id=ORDERS, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_24HR, limit=100000, time_interval=ONE_DAY),
    # Weighted Limits
    RateLimit(limit_id=SNAPSHOT_PATH_URL, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 50)]),
    RateLimit(limit_id=BINANCE_CREATE_ORDER, limit=MAX_REQUEST, time_interval=ONE_MINUTE,
              linked_limits=[LinkedLimitWeightPair(REQUEST_WEIGHT, 1),
                             LinkedLimitWeightPair(ORDERS, 1),
                             LinkedLimitWeightPair(ORDERS_24HR, 1)]),
]
```

!!! note
    Binance implements API Pools as well as weighted requests. In the example above, the `BINANCE_CREATE_ORDER` endpoint has a request weight of 1 for 3 API Pools, while the `SNAPSHOT_PATH_URL` endpopint has a request weight of 50 for the `REQUEST_WEIGHT` API Pool. Notice that the API Pools have different rate limits and time intervals.

## Integrating Rate Limits into the connector

The throttler should be consumed by all relevant classes that issue server API calls that are limited by the exchange (either http requests or websocket requests). Namely the `Exchange/Derivative`, `APIOrderBookDataSource` and `UserStreamDataSource` classes. Doing so ensures that the throttler manages all REST API/Websocket requests issued by any of the connector components.

In this example, we will use referencing the `NdaxExchange` class.

### Initializing the Connector

In the ```__init__()``` function, we have to initialize the `AsyncThrottler`.

```python
from hummingbot.connector.exchange.ndax import ndax_constants as CONSTANTS

class NdaxExchange(ExchangeBase):
    def __init__(...):
        ...
        self._throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self._order_book_tracker = NdaxOrderBookTracker(
                throttler=self._throttler, trading_pairs=trading_pairs, domain=domain
        )
        self._user_stream_tracker = NdaxUserStreamTracker(
            throttler=self._throttler, auth_assistant=self._auth, domain=domain
        )
```

!!! note
    Notice that we pass the throttler as arguments to the `NdaxOrderBookTracker` as well as `NdaxUserStreamTracker`. This is to ensure that all classes that interact with the Ndax API servers share the same throttler.

### Consuming the throttler

To consume the throttler when executing an API request, we simply wrap the contents of the `_api_request(...)` function within the asynchronous context as seen below.


```python
def _api_request(...):
  async with self._throttler.execute_task(path_url):
    ...
```

!!! warning
    The `path_url` must be match the `limit_id` of the endpoint as defined in the `RATE_LIMITS` constant. The throttler will match the `path_url` to its assigned rate limits or API pools.

## Client Configurations

The steps below are required so the Hummingbot client would recognise the new connector package.

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
