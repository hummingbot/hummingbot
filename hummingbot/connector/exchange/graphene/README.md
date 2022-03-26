# High Level Overview of Graphene >> Metanode >> Hummingbot

## Graphene

Graphene is a blockchain which provides specific public api calls.
Many of these calls rely upon the user holding cached information from other calls to decipher.
We use the following api calls:

network_broadcast/

 - broadcast_transaction_with_callback

history/

 - get_fill_order_history

 - get_relative_account_history

database/

 - get_account_by_name

 - get_chain_properties

 - get_dynamic_global_properties

 - get_full_accounts

 - get_named_account_balances

 - get_objects

 - get_order_book

 - get_required_fees

 - get_ticker

 - get_trade_history

 - get_transaction_hex

 - lookup_asset_symbols

# Metanode

Metanode is an API layer that exists between Graphene Public API Nodes and the user.

It provides streaming statistically validated data from Graphene blockchain public API nodes.

This data resides in a SQL database.

Where pertinent, information is cached once, however, if the data is streaming it is updated as frequently as possible - given network and statistical confirmation restraints.

The Metanode API is designed to act more like a "Centralized Exchange" than dealing with a blockchain.  Graphene based fraction math is replaced with human readable floats.  Excess blockchain data, from a trading perspective, is stripped.  The Metanode is built to be as "trading bot builder" friendly as possible from the client perspective, as opposed to Graphene, which is built to be as efficient as possible from the server perspective.  This change in perspective makes for clean upstream implementation.

the Metanode data API is used by accessing `@property` methods of the `GrapheneTrustlessClient` class,

```python
metanode = GrapheneTrustlessClient()
```

which exposes the following properties that make discrete SQL database queries:

 - metanode.chain -> dict: ["id", "name"]

 - metanode.account -> dict: ["id", "name", "fees_account", "ltm", "cancels"]

 - metanode.assets -> dict: ["id", "fees_asset", "balance", "precision", "supply"]

 - metanode.objects -> dict: ["name", "precision"]

 - metanode.pairs -> dict: ["id", "last", "book", "history", "ops", "fills", "opens"]

 - metanode.nodes -> dict: ["ping", "code", "status", "handshake"]

 - metanode.timing -> dict: ["ping", "read", "begin", "blocktime", "blocknum", "handshake"]

 - metanode.whitelist -> list: ["wss://", "wss://", ...]

The Metanode also provides transaction signing for limit_order_create and limit_order_cancel Graphene operations.  The ECDSA occurs _without_ the use of the 2+MB `python-graphene` dependency:

```python
auth = GrapheneAuth() # exposes the following class methods which allows for order headers to be created and execution to occur

# create an order dictionary with appropriate header
order = auth.prototype_order()

# add edicts to the order demanding buy/sell/cancel/login
# sample login
order1["edicts"] = [{"op": "login"}]
# sample cancel all
order2["edicts"] = [{"op": "cancel", "ids": ["1.7.X"]}]
# sample place two limit orders
order3["edicts"] = [
    {"op": "buy", "amount": 10, "price": 0.2, "expiration": 0,},
    {"op": "sell", "amount": 10, "price": 0.7, "expiration": 0,},
]
# then execution occurs in a parallel process using the broker method
result = broker(order)
```

## Hummingbot

Hummingbot (with graphene modifications) is an execution engine which provides:

 - cli for bot creation
 - a recurring "tick" loop which allows for automated trading
 - live orderbooks
 - account balances
 - orderbook post processing in cython
 - buy/sell/cancel authenticated ops
 - order tracking with both client ID and exchange ID
 - - as logical translation from graphene opens/fills/creates/cancels
 - - and with respect to known buy/sell/cancel attempts
