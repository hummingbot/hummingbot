# Task 1 — OrderBookTracker & Data Source

![OrderBookTrackerUMLDiagram](/assets/img/order-book-tracker-architecture.svg)

The **_UML Diagram_**, given above, illustrates the relations between `OrderBookTracker` and its subsidiary classes.

The first 2 components to begin:

- `OrderBookTracker`
- `OrderBookTrackerDataSource`

## OrderBookTracker

The `OrderBookTracker` contains subsidiary classes that help maintain the real-time order book of a market.
Namely, the classes are `OrderBookTrackerDataSource`, `OrderBook` and `OrderBookMessage`.

Integrating a new exchange connector requires you to extend from the `OrderBookTracker` base class [here](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book_tracker.py)

The following details are **required** functions to be implemented in `OrderBookTracker`:

### `exchange_name`

This function returns the appropriate exchange name

**Input Parameter(s):** `None` <br/> **Expected Output(s):** `str`

### `tracking_single_order_book`

This function applies the snapshot/diff messages received from `OrderBookDataSource` into the appropriate `OrderBook` for any given trading pair.
Notice that `OrderBookTracker` maintains a dictionary of `OrderBook's that can be identified by the trading pair.

**Input Parameter(s):** trading_pair: `str` <br/> **Expected Output(s):** `None`

## OrderBookTrackerDataSource

The `OrderBookTrackerDataSource` class is responsible for making API calls and/or WebSocket queries to obtain order book snapshots, order book deltas, and miscellaneous information on the order book.

Integrating your data source component requires you to extend from the `OrderBookTrackerDataSource` base class [here](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/core/data_type/order_book_tracker_data_source.py).

The following details the **required** functions in `OrderBookTrackerDataSource`:

### `fetch_trading_pairs`

Performs the necessary API request(s) to get all the active trading pairs being traded on the exchange.
It is also expected that the trading pairs are converted into Hummingbot's `BaseAsset-QuoteAsset` format (i.e. `ETH-USDT`)

**Input Parameter(s):** `None` <br/> **Expected Output(s):** `Dict[str, float]`

### `get_last_traded_prices`

Performs the necessary API request(s) to get the last traded price for the given markets (trading_pairs) and return a dictionary of `trading_pair` its last traded price.

**Input Parameter(s):** trading_pairs: `List[str]`<br/>
**Expected Output(s):** `Dict[str, float]`

### `get_snapshot`

Fetches order book snapshot for a particular trading pair from the exchange REST API.<br/>

!!! note
    Certain exchanges do not add a timestamp/nonce to the snapshot response. In this case, to maintain a real-time order book would require generating a timestamp for every order book snapshot and delta messages received and applying them accordingly. In the [Bittrex connector](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector), this is performed by invoking the `queryExchangeState` topic on the SignalR WebSocket client.

**Input Parameter(s):** client: `aiohttp.ClientSession`, trading_pair: `str` <br/>
**Expected Output(s):** `Dict[str, any]`

### `get_new_order_book`

Create a new `OrderBook` instance and populate its `bids` and `asks` by applying the order_book snapshot to the order book.
This might involve calling `convert_snapshot_message_to_order_book_row()` from the utils script file to parse the raw API repsonse from the exchange.

**Input Parameter:** trading_pair: `str` <br/>
**Expected Output(s):** `OrderBook`

!!! note
    Certain exchanges do not add a timestamp/nonce to the snapshot response. In this case, to maintain a real-time order book would require generating a timestamp for every order book snapshot and delta messages received and applying them accordingly. In the [Bittrex connector](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector), this is performed by invoking the `queryExchangeState` topic on the SignalR WebSocket client.

### `listen_for_trades`

Subscribes to the trade channel of an exchange. Adds incoming messages(of filled orders) to the `output` queue, to be processed by `OrderBookTracker` (in `_emit_trade_event_loop`)

**Input Parameter:** ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` <br/>
**Expected Output(s):** None

### `listen_for_order_book_diffs`

Fetches or Subscribes to the order book snapshots for each trading pair. Additionally, parses the incoming message into an `OrderBookMessage` and appends it into the `output` Queue.

**Input Parameter:** ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` <br/>
**Expected Output(s):** None

### `listen_for_order_book_snapshots`

Fetches or Subscribes to the order book deltas(diffs) for each trading pair. Additionally, parses the incoming message into an `OrderBookMessage` and appends it into the `output` Queue. |

**Input Parameter:** ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` <br/>
**Expected Output(s):** None

!!! note
    In certain cases, the 3 `listen_for_` coroutines could be combined into 1 single coroutine. An example could be seen in the [Crypto.com connector](https://github.com/CoinAlpha/hummingbot/blob/8ac56466b606f7780d448ab14b24cd0f9e40d94a/hummingbot/connector/exchange/crypto_com/crypto_com_api_user_stream_data_source.py#L37).

## OrderBook

The `OrderBook` is an interface class that contains all the necessary functions and variables to maintain an order book of the specified trading pair.
Implementing an exchange connector requires its own order book class that extends from the `OrderBook`.

The following details are **required** functions to be implemented in the new `OrderBook` class:

### `snapshot_message_from_exchange`

Converts json snapshot data from the exchange into standard `OrderBookMessage` format.

**Input Parameter(s):** msg: `Dict[str, any]`, timestamp: `float`, metadata: `Optional[Dict] = None` <br/>
**Expected Output(s):** `OrderBookMessage`

### `diff_message_from_exchange`

Converts json diff data from the exchange into standard `OrderBookMessage` format.

**Input Parameter(s):** msg: `Dict[str, any]`, timestamp: `float`, metadata: `Optional[Dict] = None` <br/>
**Expected Output(s):** `OrderBookMessage`

### `trade_message_from_exchange`

Converts json trade data from the exchange into standard `OrderBookMessage` format.

**Input Parameter(s):** msg: `Dict[str, any]`, timestamp: `float`, metadata: `Optional[Dict] = None` <br/>
**Expected Output(s):** `OrderBookMessage`

!!! note
    The functions mentioned above will have to be adequately adjusted based on the data provided by the exchange API. Using `metadata` to include additional information into `content` might be useful if data(i.e. timestamp) is not provided by the exchanges API.

## OrderBookMessage

The `OrderBookMessage` is an abstract class that stores the relevant order book information obtained from either the exchange or a local db.
Integrating a new exchange connector will require implementing its own class that extends from `OrderBookMessage`.

The `OrderBookMessage` base class contains 3 main attributes, namely:

- type: `OrderBookMessageType`<br/>
  Specified and differentiate the messages from `SNAPSHOT`, `DIFF` and `TRADE` types.

- content: `Dict[str, any]`<br/>
  Contains the API response for snapshot, diff and trades in a JSON format.

- timestamp: `float`<br/>
  Defines the time in which the message is received.

The following details are **required** functions to be implemented in the new `OrderBookMessage` class:

### `update_id`

Only relevant for `OrderBookMessageType.DIFF` and `OrderBookMessageType.SNAPSHOT` messages.
This id is either the timestamp or the message nonce of the message.

### `trade_id`

Only relevant for `OrderBookMessageType.TRADE` messages. This id is either the trade id itself or the timestamp of the message.

### `trading_pair`

Specifies the trading pair in which this order book message is associated to.

### `asks`

Only relevant for `OrderBookMessageType.DIFF` and `OrderBookMessageType.SNAPSHOT` messages.
List of all the order book entries on the ask side.

### `bids`

Only relevant for `OrderBookMessageType.DIFF` and `OrderBookMessageType.SNAPSHOT` messages.
List of all the order book entries on the bid side.

## Utility Functions

It contains any miscellaneous functions that are not completely associated with the classes defined in the overall architecture but necessary for Hummingbot to perform its functions adequately.
These are stored in the `*_utils.py` file.

Below are some examples of such functions:

| Function(s)                                    | Description                                                                                                     |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `convert_snapshot_message_to_order_book_row()` | Performs the necessary conversion from `OrderBookMessage` to a `Tuplep[List[OrderBookRow]]`                     |
| `get_new_client_order_id()`                    | Generates a Hummingbot client order id from which it does its own tracking.                                     |
| `convert_from_exchange_trading_pair()`         | Converts the exchange's trading pair to `[Base]-[Quote]` formats and return the output.                         |
| `convert_to_exchange_trading_pair()`           | Converts HB's `[Base]-[Quote]` trading pair format to the exchange's trading pair format and return the output. |

!!! note
    The `convert_from/to_exchange_trading_pair()` functions are only required if the exchange does not provide trading pairs in `Base-Quote` format.

For reference you can refer to [Crypto.com](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/crypto_com/crypto_com_utils.py) or [ProBit](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/probit/probit_utils.py).

## Exchange Constants

It contains all the constant variables associated with an exchange.

Below are some examples of such variables

| Variables(s)          | Type        | Description                                                   |
| --------------------- | ----------- | ------------------------------------------------------------- |
| `EXCHANGE_NAME`       | `str`       | Name used to identify the exchange throughout Hummingbot.     |
| `REST_URL`            | `str`       | Base URL for the exchange's REST API.                         |
| `WS_PRIVATE_CHANNELS` | `List[str]` | List of all the WebSocket channels that an exchange provides. |
| `ORDER_STATUSES`      | `List[str]` | List of all the order statuses as defined by the exchange.    |

For reference you can refer to [Crypto.com](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/crypto_com/crypto_com_utils.py) or [ProBit](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/probit/probit_utils.py).

## Debugging & Testing

As part of the QA process, for each task (Task 1 through 3), you are **required** to include the unit test cases for the code review process to begin.
Refer to [Option 1: Unit Test Cases](/developer/debug&test/#option-1-unit-test-cases) to build your unit tests.
