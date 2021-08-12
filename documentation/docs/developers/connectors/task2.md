# Task 2 — UserStreamTracker & Authentication

![UserStreamTrackerUMLDiagram](/assets/img/user-stream-tracker-architecture.svg)

The **_UML Diagram_**, given above, illustrates the relations between `UserStreamTracker` and its subsidiary classes.

The `UserStreamTracker` responsibility is to fetch user account data and queues it accordingly.

`UserStreamTracker` contains subsidiary classes that help maintain the real-time wallet/holdings balance and open orders of a user. Namely, the classes required are:

- `UserStreamTrackerDataSource`
- `UserStreamTracker`
- `Auth`(if applicable).

!!! note
    Auth is generally only required in **Centralized Exchanges**

## UserStreamTrackerDataSource

![UserStreamTrackerDataSourceClassDiagram](/assets/img/user-stream-tracker-datasource-class-diagram.svg)

The `UserStreamTrackerDataSource` class is responsible for initializing a WebSocket connection to obtain user order, trade, and balances updates.
Implementing an exchange connector would require you to create its own data source that extends from the `UserStreamTrackerDataSource` base class here.

Below are some variable(s) and its respective description that you might find useful when creating a connector:

| Variable(s)       | Type            | Description                                                                          |
| ----------------- | --------------- | ------------------------------------------------------------------------------------ |
| `_domain`         | `Optional[str]` | Denotes the base domain for all REST API requests and WS connections.                |
| `_last_recv_time` | `float`         | The timestamp(in ms) of the last user data message received by the websocket client. |
| `_auth`           | `Auth`          | The `Auth` class used by the `UserStreamTrackerDataSource`.                          |

!!! tip
    For an example on `_domain` you can refer to [Binance](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/binance/binance_user_stream_tracker.py) or [ProBit](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/probit/probit_user_stream_tracker.py).

The following details the **required** functions in `UserStreamTrackerDataSource`: <br/>

### `last_recv_time`

A property function that retrieves the timestamp(in ms) of the last user data message received by the WebSocket client.
Should be updated(using python's `time.time()` or using the message timestamp) everytime message is received from the WebSocket.<br/>

**Input Parameter:** None <br/>
**Expected Output(s):** `float`

### `listen_for_user_stream`

An **_abstract_** function from the `UserTrackerDataSource` base class that **must** be implemented.
Subscribes to all relevant user channels via web socket, and keeps the connection open for incoming messages.<br/>

**Input Parameter:** ev_loop: `asyncio.BaseEventLoop`, output: `asyncio.Queue` <br/>
**Expected Output(s):** None

## UserStreamTracker

![UserStreamTrackerClassDiagram](/assets/img/user-stream-tracker-class-diagram.svg)

The `UserStreamTracker` class is responsible for capturing the user's account balances and orders. It simply parses and queues the messages to be processed by the `Exchange` class.

This can be achieved in 2 ways(depending on the available API on the exchange):

1. **REST API**

   In this scenario, we would have to periodically make API requests to the exchange to retrieve information on the user's **account balances** and **order statuses**.
   An example of this can be seen in [Huobi's connector exchange file](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/huobi/huobi_exchange.pyx) connector.

   As seen in the `Exchange` class, Huobi uses REST API alone by periodically calling the market's `_update_balances()` and `_update_order_status()` through the `_status_polling_loop()`.
   Also, it can be seen that no user stream files exist in Huobi's connector directory.

!!! warning
    Maintaining user data using just the REST API is not ideal and would generally lead to degraded performance of the bot.

2. **WebSocket API**

   When an exchange does have WebSocket API support to retrieve user account details and order statuses, it would be ideal to incorporate it into the Hummingbot client when managing account balances and to update order statuses.
   This is especially important since Hummingbot needs to know the available account balances and order statuses at all times.

!!! tip
    In most scenarios, as seen in most other Centralized Exchanges(i.e. [Binance](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/binance/binance_user_stream_tracker.py), [Crypto.com](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/crypto_com/crypto_com_user_stream_tracker.py), [ProBit](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/connector/exchange/probit/probit_user_stream_tracker.py)), a simple WebSocket integration is used to listen on selected topics and retrieving messages to be processed in `Exchange` class.

The following details the **required** functions to be implemented in `UserStreamTracker`:

### `data_source`

Initializes a user stream data source. <br/>

**Input Parameter:** None <br/>
**Expected Output(s):** `UserStreamTrackerDataSource`

### `start`

Starts all listeners and tasks. <br/>

**Input Parameter:** None <br/>
**Expected Output(s):** None

## Authentication

![AuthClassDiagram](/assets/img/auth-class-diagram.svg)

Tracking a user's orders, trades and balance generally require authentication tied to each request or a WebSocket connection.
Hence it would only make sense to have a dedicated module to handle the generation of request signatures(REST API) or authentication payloads(WebSocket API).

The `Auth` class is responsible for creating the necessary request headers and/or data bodies necessary to authenticate said request/WebSocket connection.

!!! note
    Although mainly used in the `Exchange` class, it is generally required here in the `UserStreamTrackerDataSource`.

Below are some variable(s) and its respective description that you might find useful when creating a connector:

| Variable(s)  | Type            | Description                                                                                               |
| ------------ | --------------- | --------------------------------------------------------------------------------------------------------- |
| `api_key`    | `str`           | The user's API Key for the exchange.                                                                      |
| `secret_key` | `str`           | The user's API Secret for the exchange.                                                                   |
| `passphrase` | `Optional[str]` | The passphrase associated to said API key. An optional variable depending on the exchange specifications. |
| `domain`     | `Optional[str]` | Denotes the base domain for all REST API requests and WS connections.                                     |
| `auth_token` | `Optional[str]` | The OAuth token associated to a user. An optional variable depending on the exchange specifications.      |

The following details the **required** functions to be implemented in `Auth`:

### `generate_auth_dict`

Generates the necessary auth headers and its corresponding values for an API request. <br/>

**Input Parameter:** `Any` <br/>
**Expected Output(s):** `Dict[str, Any]`

### `get_ws_auth_payload`

Generates the authentication payload required to established a authenticated websocket connection. <br/>

**Input Parameter:** `Any` <br/>
**Expected Output(s):** `Dict[str, Any]`

!!! warning
    The details on how to correctly generate the request signature and websocket auth payload is determined by the exchange.

## Debugging & Testing

As part of the Code Review and QA process, for each task (Task 1 through 3), you are **required** to include the unit test cases for the code review process to begin.
Refer to [Option 1: Unit Test Cases](/developer/debug&test/#option-1-unit-test-cases) to build your unit tests.
