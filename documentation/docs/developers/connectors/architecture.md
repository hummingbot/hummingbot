# Connector Architecture

![Connector Architecture Diagram](/assets/img/connector-architecture-diagram.svg)

The **_Architecture Diagram_**, given above, depicts the high-level design of a Connector. Given below is a quick overview of each component. 

## Class Components

Each exchange connector is comprised of the following components:
Below are the general tasks that each class component has to fulfil. 

Class | Task(s)
----|----
**OrderBookTrackerDataSource**<br/>*REQUIRED* | Responsible for retrieving all the data from the connector's API server. Does initital parsing before being processed by `OrderBookTracker`.
**OrderBookTracker**<br/>*REQUIRED* | Responsible for processing the data obtained from the data source. Maintains a copy of the market's real-time order book.
**Market**<br/>*REQUIRED* | Responsible for executing buy, sell and cancel orders. 
**InFlightOrder**<br/>*REQUIRED* | Stores all details and state of an order.
**UserStreamTracker** | Responsible for processing orders and account balances data specific to the user on a particular exchange.
**MarketAuth** | Responsible for signing certain requests to authenticate the user requests.
**OrderBookTrackerEntry**<br/>*REQUIRED* | Stores the order book of a particular market.
**OrderBookMessage**<br/>*REQUIRED* | Represents a message response from the exchange API servers.
**ActiveOrderTracker** | Mainly used by DEXes to keep track of orders. Also converts API responses to a `OrderBookRow` that would be used to maintain the real-time order book.

## Directory and File Structure

Each exchange connector consists of the following files:

```
hummingbot/market/<market_name> # folder for specific exchange
├── *_market.[pyx,pxd]                    
├── *_auth.py                      
├── *_data_source.py               
├── *_order_book.[pyx,pxd]                
├── *_order_book_tracker.py        
├── *_active_order_tracker.[pyx,pxd]
├── *_user_stream_tracker.py 
└── *_in_flight_order.[pyx,pxd]
```

## Component Overview

Below 

Component<div style="width: 210px"/>                     | Description
:--------------------------------------------------------|-------------
`*_market.pyx`                                           | Connector modules are centered around a `Market` class, which are children of [`MarketBase`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/market_base.pyx). Each `Market` class contains a separate `OrderBookTracker` and `UserStreamTracker` to pass along changes to the relevant order books and user accounts, respectively.<br/><br/>`Market` instances also contain a list of `InFlightOrders`, which are orders placed by Hummingbot that are currently on the order book. Typically, it is also helpful to have a market-specific `Auth` class, which generates the necessary authentication parameters to access restricted endpoints, such as for trading.
`*_auth.py`                                              | This class handles the work of creating access requests from information provided by Hummingbot. Arguments tend to include: <ul><li>HTTP Request Type<li>Endpoint URL<li>Mandatory parameters to pass on to the exchange (e.g. API key, secret, passphrase, request body)</ul><br/>Depending on the specific exchange, different information may be needed for authentication. Typically, the `Auth` class will:<ul><li>Generate a timestamp.<li>Generate a signature based on the time, access method, endpoint, provided parameters, and private key of the user.<li>Compile the public key, timestamp, provided parameters, and signature into a dictionary to be passed via an `http` or `ws` request.</ul><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This module is typically required for centralized exchange only.  Generally, auth for DEXs is handled by the respective `wallet`.</td></tr></tbody></table>
`*_order_book_tracker.py`<br/>`*_user_stream_tracker.py` | Each `Market` class contains an `OrderBookTracker` and a `UserStreamTracker`, to maintain a real-time order book of a particular trading pair and to access and maintain the current state of the user’s account and orders respectively.<br/>Both the `OrderBookTracker` and `UserStreamTracker` have subsidiary classes which handle data retrieval and processing.<ul><li>`OrderBookTrackerDataSource` and `UserStreamDataSource` classes contain API calls to pull data from the exchange and user accounts and WebSocket feeds to capture state changes.<li>The `OrderBook` class contains methods which convert raw snapshots from exchanges into usable dictionaries of active bids and asks.</ul>
`*_order_book_data_source.py`                            | Consists of the `OrderBookTrackerDataSource` class. This class is responsible for initializing the initial `OrderBook` and also deals with order book data retrieval. It simply collects, parses and queues the data stream to be processed by `OrderBookTracker`. Generally, this would mean pulling data from the exchange's API/WebSocket servers.</br></br>To maintain a consistent and up-to-date order book, it is necessary to track the timestamp of each message received from the exchange API servers. Depending on the exchange responses, we can maintain an order book in the following ways:<ol><li>Presence of Timestamp/Nonce<br/>In this ideal scenario, we will only 'apply' delta messages onto the order book if and only if the timestamp of the message received is **above** or **+1** of `_last_diff_uid` in the order book.</li><li>Absence of Timestamp/Nonce<br/>In this scenario, we would have to assign a timestamp to every message received from the exchange and similarly apply the delta messages sequentially only if it is received after the snapshot message.</li></ol><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: It is important that the order book being maintained reflects all changes and is consistent with the order book in the exchange. As a safeguard/fallback, in the event when Hummingbot is unable to adequately maintain the order book, executing periodic order book snapshot requests can help to ensure that any deltas missed would be corrected.</td></tr></tbody></table>
`*_user_stream_data_source.py`                           | The `UserStreamTrackerDataSource` class deals with user data retrieval. It simply collects, parses and queues the data stream to be processed by `UserStreamTracker`.<br/><br/>Unlike `OrderBookTrackerDataSource`, `UserStreamTrackerDataSource` retrieves messages pertaining to user account balances and orders. 
`*_active_order_tracker.pyx`                             | Mainly deals with tracking of an open order placed by the user. It also consists of functions like `convert_snapshot_message_to_order_book_row` and `convert_diff_message_to_order_book_row` to help parse the incoming data that will be subsequently used by `OrderBookTrackerDataSource` and `OrderBookTracker` to maintain a real-time order book.<br/><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This class is not necessary for all exchanges</td></tr></tbody></table>
`*_in_flight_order.pyx`                                  | Stores all details pertaining to the current state of an order. <table><tbody><tr><td bgcolor="#ecf3ff">**Note**: It is important to keep a consistent and accurate state of all active orders placed by the user. This ensures that the strategies are given the correct information and are able to perform their tasks accordingly.</td></tr></tbody></table>
