# Debugging & Testing

This section will breakdown some of the ways to debug and test the code. You are not entirely required to use the options during your development process.

!!! warning
    As part of the QA process, for each tasks(Task 1 through 3) you are **required** to include the unit test cases for the code review process to begin. Refer to [Option 1: Unit Test Cases](/developers/connectors/task4/#option-1-unit-test-cases) to build your unit tests.
    
## Option 1. Unit Test Cases

For each tasks(1->3), you are required to create a unit test case. Namely they are `test_*_order_book_tracker.py`, `test_*_user_stream_tracker.py` and `test_*_market.py`. 
Examples can be found in the [test/integration](https://github.com/CoinAlpha/hummingbot/tree/master/test/integration) folder.

Below are a list of items required for the Unit Tests:

### 1. Data Source & Order Tracker | `test_*_order_book_tracker.py`

The purpose of this test is to ensure that the `OrderBookTrackerDataSource` and `OrderBookTracker` and all its functions are working as intended.
Another way to test its functionality is using a Debugger to ensure that the contents `OrderBook` mirrors that on the exchange.

### 2. User Stream Tracker | `test_*_user_stream_tracker.py`

The purpose of this test is to ensure that the `UserStreamTrackerDataSource` and `UserStreamTracker` components are working as intended.
This only applies to exchanges that has a WebSocket API. As seen in the examples for this test, it simply outputs all the user stream messages. 
It is still required that certain actions(buy and cancelling orders) be performed for the tracker to capture. Manual message comparison would be required.

#### Example

Placing a single LIMIT-BUY order on Bittrex Exchange should return the following (some details are omitted):

```Bash tab="Order Detail(s)"
Trading Pair: ZRX-ETH
Order Type: LIMIT-BUY
Amount: 100ZRX
Price: 0.00160699ETH
```

```Bash tab="Action(s) Performed"
1. Placed LIMIT BUY order.
2. Cancel order.
```

```Bash tab="Expected output"
# Below is the outcome of the test. Determining if this is accurate would still be necessaru.

<Queue maxsize=0 _queue=[
    BittrexOrderBookMessage(
        type=<OrderBookMessageType.DIFF: 2>, 
        content={
            'event_type': 'uB',
            'content': {
                'N': 4,
                'd': {
                    'U': '****', 
                    'W': 3819907,
                    'c': 'ETH',
                    'b': 1.13183357, 
                    'a': 0.96192245, 
                    'z': 0.0,
                    'p': '0x****',
                    'r': False, 
                    'u': 1572909608900,
                    'h': None
                }
            }, 
            'error': None, 
            'time': '2019-11-04T23:20:08'
        },
        timestamp=1572909608.0
    ), 
    BittrexOrderBookMessage(
        type=<OrderBookMessageType.DIFF: 2>,
        content={
            'event_type': 'uO',
            'content': {
                'w': '****',
                'N': 44975,
                'TY': 0,
                'o': {
                    'U': '****',
                    'I': 3191361360,
                    'OU': '****',
                    'E': 'XRP-ETH',
                    'OT': 'LIMIT_BUY',
                    'Q': 100.0,
                    'q': 100.0,
                    'X': 0.00160699,
                    'n': 0.0,
                    'P': 0.0,
                    'PU': 0.0,
                    'Y': 1572909608900,
                    'C': None,
                    'i': True,
                    'CI': False,
                    'K': False,
                    'k': False,
                    'J': None,
                    'j': None,
                    'u': 1572909608900,
                    'PassthroughUuid': None
                }
            },
            'error': None,
            'time': '2019-11-04T23:20:08'
        }, 
        timestamp=1572909608.0
    ),
    BittrexOrderBookMessage(
        type=<OrderBookMessageType.DIFF: 2>,
        content={
            'event_type': 'uB',
            'content': {
                'N': 5,
                'd': {
                    'U': '****',
                    'W': 3819907,
                    'c': 'ETH', 
                    'b': 1.13183357, 
                    'a': 1.1230232,
                    'z': 0.0,
                    'p': '****',
                    'r': False,
                    'u': 1572909611750,
                    'h': None
                }
            }, 
            'error': None, 
            'time': '2019-11-04T23:20:11'
        }, 
        timestamp=1572909611.0
    ), 
    BittrexOrderBookMessage(
        type=<OrderBookMessageType.DIFF: 2>,
        content={
            'event_type': 'uO',
            'content': {
                'w': '****',
                'N': 44976, 
                'TY': 3, 
                'o': {
                    'U': '****', 
                    'I': 3191361360, 
                    'OU': '****', 
                    'E': 'XRP-ETH', 
                    'OT': 'LIMIT_BUY', 
                    'Q': 100.0, 
                    'q': 100.0, 
                    'X': 0.00160699, 
                    'n': 0.0, 
                    'P': 0.0, 
                    'PU': 0.0, 
                    'Y': 1572909608900, 
                    'C': 1572909611750, 
                    'i': False, 
                    'CI': True,
                    'K': False,
                    'k': False, 
                    'J': None, 
                    'j': None, 
                    'u': 1572909611750, 
                    'PassthroughUuid': None
                }
            }, 
            'error': None, 
            'time': '2019-11-04T23:20:11'
        }, 
        timestamp=1572909611.0
    )
] tasks=4>
```

### 3.  Exchange Class Unit Tests | `test_*_exchange.py`

The purpose of this test is to ensure that all components and the order life cycle are working as intended. This test determines if the connector can place and manage orders.
All the tests below must pass successfully on both real API calls and mocked API calls mode.

The mocked API calls mode facilitates testing where we can run tests as often as we want without incurring costs in transactions and slippage. In the mocked mode, we simulate any API calls where exchange API key and secret are required,
i.e. in this mode, all the tests should pass without using real exchange API credentials.

To simulate REST API responses, please use `test.integration.humming_web_app.HummingWebApp`. The key steps to follow are as below:

#### Create environment variables
* `MOCK_API_ENABLED` - true or false - to indicate whether to run the tests in mocked API calls mode
* `NEW_EXCHANGE_API_KEY` - string - the exchange API key
* `NEW_EXCHANGE_API_SECRET` - string - the exchange API secret

In `test_*_market.py`:

```python
import conf
.
.
.
API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
API_KEY = "XXX" if API_MOCK_ENABLED else conf.binance_api_key
API_SECRET = "YYY" if API_MOCK_ENABLED else conf.binance_api_secret
```

#### Start Hummingbot

Configure the app on what url host to mock and which url paths to ignore, then start the app:

```python
@classmethod
def setUpClass(cls):
    cls.ev_loop = asyncio.get_event_loop()
    if API_MOCK_ENABLED:
        cls.web_app = HummingWebApp.get_instance()
        cls.web_app.add_host_to_mock(API_HOST, ["/products", "/currencies"])
        cls.web_app.start()
        cls.ev_loop.run_until_complete(cls.web_app.wait_til_started())
```

#### Patch http requests

If you use `requests` library:

```python
cls._req_patcher = mock.patch.object(requests.Session, "request", autospec=True)
cls._req_url_mock = cls._req_patcher.start()
cls._req_url_mock.side_effect = HummingWebApp.reroute_request
```

If you use `aiohttp` library:

```python
cls._patcher = mock.patch("aiohttp.client.URL")
cls._url_mock = cls._patcher.start()
cls._url_mock.side_effect = cls.web_app.reroute_local
```

#### Preset json responses

Use `update_response` to store the mocked response to the endpoint which you want to mock, e.g.

```python
cls.web_app.update_response("get", cls.base_api_url, "/api/v3/account", FixtureBinance.GET_ACCOUNT)
```

Please store your mocked json response in `test/integration/assets/mock_data/fixture_new_exchange.py`, e.g. 

```python
class FixtureBinance:
GET_ACCOUNT = {"makerCommission": 10, "takerCommission": 10, "buyerCommission": 0, "sellerCommission": 0,
                "canTrade": True, "canWithdraw": True, "canDeposit": True, "updateTime": 1580009996654,
                "accountType": "SPOT", "balances": [{"asset": "BTC", "free": "0.00000000", "locked": "0.00000000"},
                                                    {"asset": "ETH", "free": "0.77377698", "locked": "0.00000000"},
                                                    {"asset": "LINK", "free": "4.99700000", "locked": "0.00000000"}]}
```

Please remove any sensitive information from this file, e.g. your account number, keys, secrets
  
To simulate web socket API responses, please use `test.integration.humming_ws_server.HummingWsServerFactory`.

Key steps to follow are as below:<br/>
  - Start new server for each web socket connection<br/>
  ```python
  @classmethod
  def setUpClass(cls):
      cls.ev_loop = asyncio.get_event_loop()
      if API_MOCK_ENABLED:
          ws_base_url = "wss://stream.binance.com:9443/ws"
          cls._ws_user_url = f"{ws_base_url}/{FixtureBinance.GET_LISTEN_KEY['listenKey']}"
          HummingWsServerFactory.start_new_server(cls._ws_user_url)
          HummingWsServerFactory.start_new_server(f"{ws_base_url}/linketh@depth/zrxeth@depth")
   ```

#### Patch `websockets`

```python
cls._ws_patcher = unittest.mock.patch("websockets.connect", autospec=True)
cls._ws_mock = cls._ws_patcher.start()
cls._ws_mock.side_effect = HummingWsServerFactory.reroute_ws_connect
```

#### Send json responses

In the code where you are expecting json response from the server:

```python
HummingWsServerFactory.send_json_threadsafe(self._ws_user_url, data1, delay=0.1)
HummingWsServerFactory.send_json_threadsafe(self._ws_user_url, data2, delay=0.11)
```
!!! note
    `data` is your fixture data. Make sure to set some delay if sequence of responses matters, in the above example, `data2` is supposed to arrive after `data1`.


#### Patch `get_tracking_nonce`

In cases where you need to preset `client_order_id` (our internal id), please mock it as below:

  ```python
  cls._t_nonce_patcher = unittest.mock.patch("hummingbot.market.binance.binance_market.get_tracking_nonce")
  cls._t_nonce_mock = cls._t_nonce_patcher.start()
  ```

- Mock the nonce and create order_id as required
  ```python
  self._t_nonce_mock.return_value = 10001
  order_id = f"{side.lower()}-{trading_pair}-{str(nonce)}"
  ```

Finally, stop all patchers and the web app.<br/>
Once all tests are done, stop all these services.<br/>
```python
@classmethod
def tearDownClass(cls) -> None:
  if API_MOCK_ENABLED:
      cls.web_app.stop()
      cls._patcher.stop()
      cls._req_patcher.stop()
      cls._ws_patcher.stop()
      cls._t_nonce_patcher.stop()
```

### All required tests

Below are a list of tests that are **required**:

Function | Description 
---|---
`test_get_fee` | Tests the `get_fee` function in the `Market` class. Ensures that calculation of fees are accurate.
`test_limit_buy` | Utilizes the `place_order` function in the `Market` class and tests if the market connector is capable of placing a LIMIT buy order on the respective exchange. Asserts that a `BuyOrderCompletedEvent` and `OrderFilledEvent`(s) have been captured.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Important to ensure that the amount specified in the order has been completely filled.</td></tr></tbody></table>
`test_limit_sell` | Utilizes the `place_order` function in the `Market` class and tests if the market connector is capable of placing a LIMIT sell order on the respective exchange.
`test_limit_maker_rejections` | Utilizes the `place_order` function in the `Market` class and tests that the exchage rejects LIMIT_MAKER orders when the prices of such orders cross the orderbook.
`test_limit_makers_unfilled` | Utilizes the `place_order` function in the `Market` class to successfully place buy and sell LIMIT_MAKER orders and tests that they are unfilled after they've been placed in the orderbook.
`test_market_buy` | Utilizes the `place_order` function in the `Market` class and tests if the market connector is capable of placing a MARKET buy order on the respective exchange.
`test_market_sell` | Utilizes the `place_order` function in the `Market` class and tests if the market connector is capable of placing a MARKET sell order on the respective exchange.
`test_cancel_order` | Utilizes the `cancel_order` function in the `Market` class and tests if the market connector is capable of cancelling an order. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: Ensures that the Hummingbot client is capable of resolving the `client_order_id` to obtain the `exchange_order_id` before posting the cancel order request. </td></tr></tbody></table>
`test_cancel_all` | Tests the `cancel_all` function in the `Market` class. All orders(being tracked by Hummingbot) would be cancelled.
`test_list_orders` | Places an order before checking calling the `list_orders` function in the `Market` class. Checks the number of orders and the details of the order. 
`test_order_saving_and_restoration` | Tests if **tracked orders** are being recorded locally and determines if the Hummingbot client is able to restore the orders.
`test_order_fill_record` | Tests if **trades** are being recorded locally.

!!! note
    Ensure that you have enough asset balance before testing. Also document the **minimum** and **recommended** asset balance to run the tests. This is to aid testing during the PR review process. Please see `test/integration/test_binance_market.py` as an example on how this task is done.

## Option 2. aiopython console
This option is mainly used to test for specific functions. Considering that many of the functions are asynchronous functions, 
it would be easier to test for these in the aiopython console. Click [here](https://aioconsole.readthedocs.io/en/latest/) for some documentation on how to use aiopython.

Writing short code snippets to examine API responses and/or how certain functions in the code base work would help you understand the expected side-effects of these functions and the overall logic of the Hummingbot client. 


### Issue a API Request
Below is just a short example on how to write a short asynchronous function to mimic a API request to place an order and displaying the response received.


```python3
# Prints the response of a sample LIMIT-BUY Order
# Replace the URL and params accordingly.

>>> import aiohttp
>>> URL="api.test.com/buyOrder"
>>> params = {
...     "symbol": "ZRXETH",
...     "amount": "1000",
...     "price": "0.001",
...     "order_type": "LIMIT"
... }
>>> async with aiohttp.ClientSession() as client:
...    async with client.request("POST",
...                              url=URL,
...                              params=params) as response:
...        if response == 200:
...            print(await response.json())

```

### Calling a Class Method
i.e. Printing the output from `get_active_exchange_markets()` function in `OrderBookTrackerDataSource`.

```python3
# In this example, we will be using BittrexAPIOrderBookDataSource

>>> from hummingbot.market.bittrex.BittrexAPIOrderBookDataSource import BittrexAPIOrderBookDataSource as b
>>> await b.get_active_exchange_markets() 

                 askRate baseAsset        baseVolume  ...             volume     USDVolume old_symbol
symbol                                                ...
BTC-USD    9357.49900000       BTC  2347519.11072768  ...       251.26097386  2.351174e+06    USD-BTC
XRP-BTC       0.00003330       XRP       83.81218622  ...   2563786.10102864  7.976883e+05    BTC-XRP
BTC-USDT   9346.88236735       BTC   538306.04864142  ...        57.59973765  5.379616e+05   USDT-BTC
.
.
.
[339 rows x 18 columns]
```

## Option 3. Custom Scripts
This option, like in Option 2, is mainly used to test specific functions. This is mainly useful when debugging how various functions/classes interact with one another.

i.e. Initializing a simple websocket connection to listen and output all captured messages to examine the user stream message when placing/cancelling an order. 
This is helpful when determining the exact response fields to use.

i.e. A simple function to craft the Authentication signature of a request. This together with [POSTMAN](https://www.getpostman.com/) can be used to check if you are generating the appropriate authentication signature for the respective requests.

### API Request: POST Order

Below is a sample code for POST-ing a LIMIT-BUY order on Bittrex. This script not only tests the `BittrexAuth` class but also outputs the response from the API server. 

```python
#!/usr/bin/env python3

import asyncio
import aiohttp
from typing import Dict
from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth

BITTREX_API_ENDPOINT = "https://api.bittrex.com/v3"

async def _api_request(http_method: str,
                       path_url: str = None,
                       params: Dict[str, any] = None,
                       body: Dict[str, any] = None,
                       ):
    url = f"{BITTREX_API_ENDPOINT}{path_url}"

    auth = BittrexAuth(
        "****",
        "****"
    )

    auth_dict = auth.generate_auth_dict(http_method, url, params, body, '')

    headers = auth_dict["headers"]

    if body:
        body = auth_dict["body"]

    client = aiohttp.ClientSession()

    async with client.request(http_method,
                              url=url,
                              headers=headers,
                              params=params,
                              data=body) as response:
        data: Dict[str, any] = await response.json()
        if response.status not in [200,201]:
            print(f"Error occurred. HTTP Status {response.status}: {data}")
        print(data)

# POST order
path_url = "/orders"

body = {
    "marketSymbol": "FXC-BTC",
    "direction": "BUY",
    "type": "LIMIT",
    "quantity": "1800",
    "limit": "3.17E-7",  # Note: This will throw an error
    "timeInForce": "GOOD_TIL_CANCELLED"
}

loop = asyncio.get_event_loop()
loop.run_until_complete(_api_request("POST",path_url=path_url,body=body))
loop.close()


```

## Option 4: Using Debugger tools.

This section will detail the necessary configurations/setup required to run the debugger tool from your IDE of choice.

### VS Code

Include the following debug configurations into the `launch.json` configuration file

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Hummingbot Application",
      "type": "python",
      "request": "launch",
      "program": "${workspaceRoot}/bin/hummingbot.py",
      "console": "integratedTerminal"
    }
  ]
}
```

By executing the `Start Debugging` command, the debugger will automatically attach itself to the Hummingbot process.
The Hummingbot app will appear in the `integratedTerminal`. You may change this as desired.

### PyCharm

Similarly, for PyCharm, you want to set up the debug configurations, as seen in the screenshot below.

![PyCharmDebugConfiguration](/assets/img/pycharm-debug-configurations.png)

!!! note
    As of this writing, there is no way to add breakpoints/log points to any of the Cython code in VSCode or PyCharm.
