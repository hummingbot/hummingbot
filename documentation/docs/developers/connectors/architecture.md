
## Connector Architecture

![Connector Architecture Diagram](/assets/img/connector-architecture-diagram.svg)

The **_Architecture Diagram_**, given above, depicts the high-level design of a Connector. Given below is a quick overview of each component. 

### Class Components

Each exchange connector is comprised of the following components:

Class | Function
----|----
**(1) OrderBookTrackerDataSource** | Responsible for retrieving all the data from the connector's API server. Does initital parsing before being processed by `OrderBookTracker`.
**(2) OrderBookTracker** | Responsible for processing the data obtained from the data source. Maintains a copy of the market's real-time order book.
**(3) UserStreamTracker** | Responsible for processing orders and account balances data specific to the user on a particular exchange.
**(4) Market** | Responsible for executing buy, sell and cancel orders. 
**(5) InFlightOrder** | Stores all details and state of an order.
**(6) MarketAuth** | Responsible for signing certain requests to authenticate the user requests.
**(7) OrderBookTrackerEntry** | Stores the order book of a particular market.
**(8) OrderBookMessage** | Represents a message response from the exchange API servers.
**(9) ActiveOrderTracker** | Mainly used by DEXes to keep track of orders. Also converts API responses to a `OrderBookRow` that would be used to maintain the real-time orderbook.

### Directory and File Structure

Each exchange connector consists of the following files:

```
hummingbot/market/<market_name> # folder for specific exchange
├── *_market.pyx                    
├── *_auth.py                      
├── *_data_source.py               
├── *_order_book.pyx                
├── *_order_book_tracker.py        
├── *_active_order_tracker.pyx 
├── *_user_stream_tracker.py 
└── *_in_flight_order.pyx
```

Component<div style="width: 170px"/>| Description
:--------------------------------------------------|-------------
`*_market.pyx`                                     | Connector modules are centered around a `Market` class, which are children of [`MarketBase`](https://github.com/CoinAlpha/hummingbot/blob/master/hummingbot/market/market_base.pyx). Each `Market` class contains a separate `OrderBookTracker` and `UserStreamTracker` to pass along changes to the relevant order books and user accounts, respectively.<br/><br/>`Market` instances also contain a list of `InFlightOrders`, which are orders placed by Hummingbot that are currently on the order book. Typically, it is also helpful to have a market-specific `Auth` class, which generates the necessary authentication parameters to access restricted endpoints, such as for trading.
`*_auth.py`                                        | This class handles the work of creating access requests from information provided by Hummingbot. Arguments tend to include: <ul><li>HTTP Request Type<li>Endpoint URL<li>Mandatory parameters to pass on to the exchange (e.g. API key, secret, passphrase, request body)</ul><br/>Depending on the specific exchange, different information may be needed for authorization. Typically, the `Auth` class will:<ul><li>Generate a timestamp.<li>Generate a signature based on the time, access method, endpoint, provided parameters, and private key of the user.<li>Compile the public key, timestamp, provided parameters, and signature into a dictionary to be passed via an `http` or `ws` request.</ul><table><tbody><tr><td bgcolor="#ecf3ff">**Note**: This module is typically required for centralized exchange only.  Generally, auth for DEXs is handled by the respective `wallet`.</td></tr></tbody></table>
`*_order_book_tracker`<br/>`*_user_stream_tracker` | Each `Market` class contains an `OrderBookTracker` to maintain a real-time order book of a particular trading pair. live data threads to exchange markets and a `UserStreamTracker` to access the current state of the user’s account and orders. Both the `OrderBookTracker` and `UserStreamTracker` have subsidiary classes which handle data access and processing.<ul><li>`OrderBookTrackerDataSource` and `UserStreamDataSource` classes contain API calls to pull data from the exchange and user accounts and WebSocket feeds to capture state changes.<li>The `OrderBook` class contains methods which convert raw snapshots from exchanges into usable dictionaries of active bids and asks.</ul>
`*_data_source.py`                                 | Each `OrderBookTracker` class contains an `OrderBookTrackerDataSource` to retrieve real-time order book data from the exchange API/WebSocket servers.
