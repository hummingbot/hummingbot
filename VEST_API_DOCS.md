# Vest API

## General API Information

The base URL endpoints are available at:

* Production: `https://server-prod.hz.vestmarkets.com/v2`
* Development: `https://server-dev.hz.vestmarkets.com/v2`

When sending requests, the header must contain:&#x20;

```json
xrestservermm: restserver{account_group}
```

### Contract Addresses

**Production**

```
VERIFYING_CONTRACT=0x919386306C47b2Fe1036e3B4F7C40D22D2461a23
```

**Development**

```
VERIFYING_CONTRACT=0x8E4D87AEf4AC4D5415C35A12319013e34223825B
```

### Symbol Conventions

* All crypto perpetual symbols are `{COIN}-PERP`, e.g. BTC-PERP, SOL-PERP
* All equities, indices, and forex perpetual symbols are `{TICKER}-USD-PERP`, e.g. AAPL-USD-PERP, SPX-USD-PERP, AUD-USD-PERP

### Format Conversions

* All decimals are strings.
* All integers are numbers.
* All timestamps are integers denoting milliseconds since epoch.
* All ambiguous monetary values like margin requirements are ubiquitously USDC. i.e. USDC is the only numéraire.

### ENUM Definitions

* Symbol status: <mark style="color:red;background-color:red;">TRADING</mark>, <mark style="color:red;background-color:red;">HALT</mark>.
* Order status: <mark style="color:red;background-color:red;">NEW</mark>, <mark style="color:red;background-color:red;">PARTIALLY\_FILLED</mark>, <mark style="color:red;background-color:red;">FILLED</mark>, <mark style="color:red;background-color:red;">CANCELLED</mark>, <mark style="color:red;background-color:red;">REJECTED</mark>.
* Order type: <mark style="color:red;background-color:red;">MARKET</mark>, <mark style="color:red;background-color:red;">LIMIT</mark>, <mark style="color:red;background-color:red;">STOP\_LOSS</mark>, <mark style="color:red;background-color:red;">TAKE\_PROFIT</mark>, <mark style="color:red;background-color:red;">LIQUIDATION</mark> (only in response).
* LP type: <mark style="color:red;background-color:red;">DEPOSIT</mark>, <mark style="color:red;background-color:red;">IMMEDIATE\_WITHDRAW</mark>, <mark style="color:red;background-color:red;">SCHEDULE\_WITHDRAW</mark>.
* Transfer type: <mark style="color:red;background-color:red;">DEPOSIT</mark>, <mark style="color:red;background-color:red;">WITHDRAW</mark>.

### Order Lifecycle

Docs coming soon.

### Order Type

Docs coming soon.

### Error Codes

```json
// General
UNAUTHORIZED = 1002
TOO_MANY_REQUESTS = 1003
INVALID_SIGNATURE = 1022
INVALID_NONCE = 1023
INVALID_NETWORK_TYPE = 1024
ACCOUNT_NOT_FOUND = 1099

// Invalid request
BAD_DECIMALS = 1111
INVALID_ORDER_TYPE = 1116
BAD_SYMBOL = 1121
INVALID_LISTEN_KEY = 1125
INVALID_PARAMETER = 1130
BAD_RECV_WINDOW = 1131
ORDER_EXPIRED = 1132
INVALID_TIME_IN_FORCE = 1133
INVALID_TRANSACTION = 1143
ALREADY_USE_TRANSACTION = 1144
INVALID_TP_SL_PRICE = 1145
INVALID_ACCOUNT_GROUP = 1146
DECLINE_WITHDRAW_FROM_MOBILE = 1147
MARKET_CLOSED = 1148

// Order rejection
PRICE_CHECK_FAILED = 3001
MARGIN_CHECK_FAILED = 3002
PRICE_STALE = 3003
ORDER_STALE = 3004
INCREASE_WITH_SL_TP = 3006
INCREASE_DURING_INSOLVENCY = 3007
DELETED_BY_LIQ = 3008
OI_CAP_EXCEEDED = 3010
INVALID_LIMIT_PRICE = 3011
DUPLICATE = 3015
ORDER_NOT_FOUND = 3017
REDUCE_ONLY_INCREASES = 3018
REDUCE_ONLY_EXCEEDS_SIZE = 3019
ORDER_CHANGES_LEVERAGE = 3020
DECREASE_LEVERAGE_WITH_POSITION = 3021
INVALID_TP_SL_PRICE = 3022
BAD_SYMBOL = 3023
MARKET_CLOSED = 3024

// LP order rejection
LP_INSUFFICIENT_BALANCE = 4001
LP_MARGIN_CHECK_FAILED = 4002
LP_PRICE_STALE = 4003
LP_ORDER_STALE = 4004
LP_WITHDRAW_WITHOUT_SHARES = 4007 
LP_DUPLICATE = 4010
LP_WITHDRAW_EXCEEDS_BALANCE = 4012

// Transfer rejection 
TRANSFER_MARGIN_CHECK_FAILED = 5002
TRANSFER_WITHDRAW_CAP_EXCEEDED = 5009
TRANSFER_DUPLICATE = 5010
TRANSFER_EXECUTION_FAILED = 5013
```

## Public REST API

### GET /exchangeInfo

#### Parameters

* *symbols* (optional: returns all by default; should be comma-separated e.g. `BTC-PERP,ETH-PERP,SOL-PERP`).

#### Notes

* The minimum contract size and contract size is 1e(-sizeDecimals).

#### Example Response

```json
{
    "symbols": [{
        "symbol": "BTC-PERP",
        "displayName": "BTC-PERP",
        "base": "BTC",
        "quote": "USDC",
        "sizeDecimals": 4,
        "priceDecimals": 2,
        "initMarginRatio": "0.1",
        "maintMarginRatio": "0.05",
        "takerFee": "0.0001",
        "isolated": false,
    }],
    "exchange": {
        "lp": "100000.000000",
        "insurance": "10000000000.000000",
        "collateralDecimals": 6,
    },
}
```

### GET /ticker/latest

#### Parameters

* *symbols* (optional: returns all by default; should be comma-separated, e.g. `BTC-PERP,ETH-PERP,SOL-PERP`).

#### Example Response

```json
{
    "tickers": [{
        "symbol": "BTC-PERP",
        "markPrice": "34000.1",
        "indexPrice": "34000.0",
        "imbalance": "123.12",
        "oneHrFundingRate": "0.0001",
        "cumFunding": "1.23",
        "status": "TRADING",
    }, ...],
}
```

### GET /ticker/24hr

#### Parameters

* *symbols* (optional: returns all by default; should be comma-separated e.g. `BTC-PERP,ETH-PERP,SOL-PERP`).

#### Example Response

```json
{
    "tickers": [{
        "symbol": "BTC-PERP",
        "openPrice": "34000.1",
        "closePrice": "33000.1",
        "highPrice": "35000.1",
        "lowPrice": "30000.1",
        "quoteVolume": "900000.12",
        "volume": "32.001",
        "priceChange": "-94.99999800", // NOTE: defined as price change from previous day's close price
        "priceChangePercent": "-95.960",
        "openTime": 1499783499040,
        "closeTime": 1499869899040,
    }, ...],
}
```

### GET /funding/history

#### Parameters

* *symbol* (e.g. `BTC-PERP`).
* *startTime* (optional).
* *endTime* (optional: defaults to current).
* *limit* (optional: defaults to 1000; maximum 1000 entries from endTime).
* *interval* (optional: defaults to  1m; supports 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M).

#### Example Response

```json
[{
        "symbol": "ETH-PERP",
        "time": 1683849600076,
        "oneHrFundingRate": "0.001000",
    },
    {
        "symbol": "ETH-PERP",
        "time": 1683849600076,
        "oneHrFundingRate": "0.001000",
    }, ...
]
```

### GET /klines

#### Parameters

* *symbol* (e.g. `BTC-PERP`).
* *startTime* (optional).
* *endTime* (optional: defaults to current).
* *limit* (optional: defaults to 1000; maximum 1000 entries from endTime).
* *interval* (optional: defaults to 1m; supports 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M).

#### Example Response

```json
[
    [
        1725315120174, // open time
        "0.098837", // o
        "0.098837", // h
        "0.098769", // l
        "0.098769", // c
        1725315151174, // close time
        "20000", // v
        "10000.000000", // quote v
        34, // num of trades
    ], ...
]
```

### GET /trades

#### Parameters

* *symbol* (e.g. `BTC-PERP`).
* *startTime* (optional).
* *endTime* (optional: defaults to current).
* *limit* (optional: defaults to 1000; maximum 1000 entries from endTime).

#### Example Response

```json
[{
    "id": 28457,
    "price": "4.00",
    "qty": "12.0000",
    "quoteQty": "48.000012",
    "time": 1499865549590,
}, ...]
```

### GET /depth

#### Parameters

* *symbol* (e.g. `BTC-PERP`).
* *limit* (optional: defaults to 20; maximum 100).

#### Example Response

```json
{
    "bids": [
        [
            "4.00", // PRICE
            "431.0000" // QTY (BASE)
        ]
    ],
    "asks": [
        [
            "4.02",
            "12.0000"
        ]
    ]
}
```

## Private REST API

## Authentication

To authenticate, the client must have access to or create the following variables:

* *primaryAddr*, the public key of your primary account which holds balances.
* *signingAddr*, a signing key generated by the client that acts as a delegate to sign transactions on behalf of the primary account.
* *apiKey*, an API key returned as the response to the POST /register endpoint.

To connect to private endpoints, the client then:

* Sends *apiKey* in the header of the request as X-API-KEY.
* Attaches a signature by a valid signing key (or primary key).
  * For each POST request, create a signature based on order parameters as specified below. It is generally recommended to use *time* as *nonce*, unless you want to create identical orders (orders whose fields are the same except for nonce).

The registration process will look like this:

1. Generate a random key/pair for signing; this will be your *signingAddr*.&#x20;

```python
from eth_account import Account
import secrets
priv = secrets.token_hex(32)
private_key = "0x" + priv
acct = Account.from_key(private_key)
print(f"My signingAddr is: {acct.address}")
```

2. Make a request to the POST /register endpoint by creating a valid signature.

<pre class="language-python"><code class="lang-python"><strong>import time
</strong><strong>from eth_account import Account as EthAccount
</strong>from eth_account.messages import encode_defunct

expiry = int(time.time()) * 1000 + 7 * 24 * 3600000  # 7 days
domain = {
    "name": 'VestRouterV2',
    "version": '0.0.1',
    "verifyingContract": VERIFYING_CONTRACT, // see contract addresses
}
types = {
    'SignerProof': [
        {'name': "approvedSigner", 'type': "address"},
        {'name': "signerExpiry", 'type': "uint256"},
    ],
}
proofArgs = {
    'approvedSigner': signing_public_key,
    'signerExpiry': expiry,
}
proofSignature = encode_typed_data(domain, types, proofArgs)
signature = EthAccount.sign_message(proofSignature, primary_private_key).signature.hex()
</code></pre>

### POST /register

#### Request Body Example

```json
{
    "signingAddr": "0x", // lower-cased
    "primaryAddr": "0x", // lower-cased
    "signature": "0x0", // = sign(signingAddr, primaryKey)
    "expiryTime": 1222222334000, // expiry time in milliseconds
    "networkType": 0
}
```

#### Example Response

```json
{
    "apiKey": abcde,
    "accGroup": 0
}
```

### GET /account

#### Parameters

* *time* (e.g. 1713593340000).

#### Example Response

```json
{
    "address": "0x3d4fcE3C4b9435C2aB6A880D37F346fa10C844e1",
    "balances": [{
        "asset": "USDC",
        "total": "4723846.892089",
        "locked": "0.000000"
    }],
    "collateral": "1333.000000",
    "withdrawable": "111222.120000",
    "totalAccountValue": "200000.120000",
    "openOrderMargin": "12222.340000", 
    "totalMaintMargin": "123232.120000",
    "positions": [{
        "symbol": "BTC-PERP",
        "isLong": true,
        "size": "0.1000",
        "entryPrice": "30.00",
        "entryFunding": "1.230000000000",
        "unrealizedPnl": "-30.000000", // includes funding
        "settledFunding": "30.000000",
        "markPrice": "30.00",
        "indexPrice": "34.00",
        "liqPrice": "20.00",
        "initMargin": "1200.000000",
        "maintMargin": "600.000000",
        "initMarginRatio": "0.2000"
    }],
    "leverages": [
        {"symbol": "BTC-PERP", "value": 20},...
    ],
    "lp": {
        "balance": "100.000000",
        "shares": "100.000000",
        "unrealizedPnl": "1.230000"
    },
    "time": 1233333333333,
    "twitterUsername": null,
    "discordUsername": null,
}
```

### GET /account/nonce

#### Parameters

* *time* (e.g. 1713593340000).

#### Example Response

```json
{
    "lastNonce": 0
}
```

### POST /account/leverage

Updates leverage on a symbol.

Parameters

* *time* (e.g. 1713593340000).
* *symbol* (e.g. "BTC-PERP).
* *value* (e.g. 10).

Example Response

```json
{
    "symbol": "BTC-PERP",
    "value": 10
}
```

### POST /orders

#### Example Signature

```python
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

args = Web3.keccak(
    encode(
        ["uint256", "uint256", "string", "string", "bool", "string", "string", "bool"],
        [time, nonce, orderType, symbol, isBuy, size, limitPrice, reduceOnly]
    )
)
signable_msg = encode_defunct(args)
signature = EthAccount.sign_message(
    signable_msg, SIGNING_PRIVATE_KEY
).signature.hex()
```

#### Request Body Example

```json
{
    "order": {
        "time": 1683849600076, // in milliseconds
        "nonce": 0,
        "symbol": "SOL-PERP",
        "isBuy": true,
        "size": "3.1200",
        "orderType": "MARKET",
        "limitPrice": "30.03",
        "reduceOnly": false,
        "timeInForce": "GTC", // (optional str: only accepted when orderType == LIMIT, must be GTC or FOK),
        "tpPrice": "31.03", // (optional str: can only be specified for LIMIT order),
        "tpSignature": "0x0", // (optional str: should be produced by setting orderType = "TAKE_PROFIT", isBuy = opposite of parent LIMIT order, limitPrice = tpPrice and reduceOnly = True),
        "slPrice": "29.03", // (optional str: can only be specified for LIMIT order), 
        "slSignature": "0x0", // (optional str: should be produced by setting orderType = "STOP_LOSS", isBuy = opposite of parent LIMIT order, limitPrice = slPrice and reduceOnly = True),
    },
    "recvWindow": 60000, // (optional int: defaults to 5000; server will discard if server ts > time + recvWindow)
    "signature": "0x0", // NOTE: make sure this starts with 0x
}
```

#### Example Response

```json
{
    "id": "0x0"
}
```

#### Example Error Response

```json
{
    "code": 429,
    "msg": "Rate limited"
}
```

### POST /orders/cancel

#### Example Signature

```python
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

args = Web3.keccak(
    encode(
        ["uint256", "uint256", "string"],
        [time, nonce, id]
    )
)
signable_msg = encode_defunct(args)
signature = EthAccount.sign_message(
    signable_msg, SIGNING_PRIVATE_KEY
).signature.hex()
```

#### Request Body Example

```json
{
    "order": {
        "time": 1683849600076,
        "nonce": 0,
        "id": "0x",
    },
    "recvWindow": 60000, // (optional int: defaults to 5000; server will discard if server ts > time + recvWindow)
    "signature": "0x0",
}
```

#### Example Response

```json
{
    "id": "0x0"
}
```

### GET /orders

#### Parameters

* *id* (optional: returns all orders by default; accepts comma-separated list of ids).
* *nonce* (optional: returns all orders by default).
* *symbol* (optional: returns all symbols by default).
* *orderType* (optional: returns all orders by default).
* *status* (optional: returns all statuses by default).
* *startTime* (optional).
* *endTime* (optional: defaults to current).
* *limit* (optional: defaults to 1000; maximum 1000 entires from endTime).
* *time* (e.g. 1713593340000).

#### Example Response

```json
[{
    "id": "0x0",
    "nonce": 0,
    "symbol": "BTC-PERP",
    "isBuy": true,
    "orderType": "LIMIT",
    "limitPrice": "30000",
    "markPrice": "30000",
    "size": "0.1000",
    "status": "FILLED",
    "reduceOnly": false,
    "initMarginRatio": "0.1250",
    "code": null, // error code, specified only if status is REJECTED
    "lastFilledSize": "0.1000", // null if status != FILLED
    "lastFilledPrice": "30000.00", // null if status != FILLED
    "lastFilledTime": 1683849600076, // null if status != FILLED
    "avgFilledPrice": "30000.00", // null if status != FILLED
    "settledFunding": "0.100000", // null if status != FILLED, positive means trader received
    "fees": "0.010000", // includes premium (and liquidation penalty if applicable)
    "realizedPnl": "0.200000", // null if status != FILLED, includes funding and fees
    "postTime": 1683849600076,
    "tpPrice": null, 
    "slPrice": null, 
}]
```

### POST /lp

#### Example Signature

```python
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

args = Web3.keccak(
    encode(
        ["uint256", "uint256", "string", "string"],
        [time, nonce, orderType, size]
    )
)
signable_msg = encode_defunct(args)
signature = EthAccount.sign_message(
    signable_msg, SIGNING_PRIVATE_KEY
).signature.hex()
```

#### Request Body Example

```json
{
    "order": {
        "time": 1683849600076,
        "nonce": 0,
        "orderType": "DEPOSIT",
        "size": "100",
    },
    "recvWindow": 60000,
    "signature": "0x0",
}
```

#### Example Response

```json
{
    "id": "0x0"
}
```

### GET /lp

#### Parameters

* *id* (optional: returns all orders by default).
* *nonce* (optional: returns all orders by default).
* *orderType* (optional: returns all orders by default).
* *status* (optional: returns all statuses by default).
* *startTime* (optional).
* *endTime* (optional: defaults to current).
* *limit* (optional: defaults to 1000; maximum 1000 entires from endTime).
* *time* (e.g. 1713593340000).

#### Example Response

```javascript
[{
    "id": "0x0",
    "nonce": 0,
    "size": "100",
    "orderType": "DEPOSIT",
    "status": "FILLED",
    "code": null, // error code, specified only if status is REJECTED
    "fees": "0",
    "postTime": 1683849600076
}]
```

### POST /transfer/withdraw

#### Example Signature

```python
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

args = Web3.keccak(
    encode(
        ["uint256", "uint256", "bool", "address", "address", "address", "uint256", "uint256"],
        [time, nonce, False, account, recipient, token, size, chainId]
    )
)
signable_msg = encode_defunct(args)
signature = EthAccount.sign_message(
    signable_msg, SIGNING_PRIVATE_KEY
).signature.hex()
```

#### Request Body Example

```json
{
    "order": {
        "time": 1683849600076,
        "nonce": 0,
        "recipient": "0x0",
        "token": "USDC",
        "size": 100000000, // uint256: should be multiplied by 1e6 for USDC
        "chainId": 324,
    },
    "execute": true, // bool: true to delegate execution to whitelisted keeper, false to execute on your own
    "recvWindow": 60000, // (optional int: defaults to 5000; server will discard if server ts > time + recvWindow)
    "signature": "0x0"
}
```

#### Example Response

```json
{
    "id": "0x0"
}
```

#### Calling \`Withdraw\` function&#x20;

If you make a request with `execute: false` , you will need to make `Withdraw` function on our treasury contract (`isSolanaNative` should be set to `false` for withdrawing to EVM network) with the arguments provided via GET `/transfer` endpoint:

```
function withdraw(
    bytes memory requestArgs,
    address signer,
    bytes memory signature,
    bytes memory signatureProof,
    bytes memory validatorSignature,
    bool isSolanaNative
) external;
```

### GET /transfer

#### Parameters

* *id* (optional: returns all orders by default).
* *nonce* (optional: returns all orders by default).
* *orderType* (optional: returns all orders by default).
* *startTime* (optional).
* *endTime* (optional: defaults to current).
* *limit* (optional: defaults to 1000; maximum 1000 entires from endTime).
* *time* (e.g. 1713593340000).

#### Example Response

```json
[{
    "id": "0x0",
    "nonce": 0,
    "size": "100",
    "orderType": "DEPOSIT",
    "status": "FILLED",
    "code": null, // error code, specified only if status is REJECTED
    "chainId": 1,
    "postTime": 1683849600076,
    
    "requestArgs": "0x00..00",
    "signer": "0x00..00",
    "signature": "0x00..00",
    "signatureProof": "0x00..00",
    "validatorSignature": "0x00..00",
}]
```

## Public WS Endpoints

The base endpoints are available at:

* Production: `wss://ws-prod.hz.vestmarkets.com/ws-api?version=1.0`
* Development: `wss://ws-dev.hz.vestmarkets.com/ws-api?version=1.0`

When sending requests, this query parameter is required:

```json
xwebsocketserver=restserver{account_group}
```

### Ping/Pong

To check the connection, the client must send `{"method": "PING", "params": [], "id": 0}` where id can be any integer. The server will respond with `{"data": "PONG"}`.

### Subscription

For each subscription, the client must attach an integer-valued id which will be unique per request. e.g. `{"method": "SUBSCRIBE", "params": [channel1, channel2, ...], "id": subscription_id}.`

The server will respond with `{"result": null, "id": subscription_id}`after successful subscription/un-subscription.

### Tickers

Channel name: <mark style="color:red;">**tickers**</mark>.

#### Example Response

```json
{
    "channel": "tickers",
    "data": [{
        "symbol": "kBONK-PERP",
        "oneHrFundingRate": "0.001250",
        "cumFunding": "1.230000000000",
        "imbalance": "10029",
        "indexPrice": "0.017414",
        "markPrice": "0.017446",
        "priceChange": "-94.999998",
        "priceChangePercent": "-95.96",
        "status": "TRADING",
    }, ]
}
```

### Klines

Channel name: <mark style="color:red;">**{symbol}@kline\_{intervals}**</mark> (e.g. DOGE-PERP\@kline\_1m).

Supported intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M.

#### Example Response

```json
{
    "channel": "DOGE-PERP@kline_1m",
    "data": [
        1725315120174, // open time
        "0.098837", // o
        "0.098837", // h
        "0.098769", // l
        "0.098769", // c
        1725315151174, // close time
        "20000", // v
        "10000", // quote v
        "34", // num of trades
    ]
}
```

### Depth

Channel name: <mark style="color:red;">**{symbol}@depth**</mark> (e.g. DOGE-PERP\@depth).

#### Example Response

```json
{
    "channel": "DOGE-PERP@depth",
    "data": {
        "bids": [
            ["0.102000", "1234"],
        ],
        "asks": [
            ["0.103000", "1234"],
        ]
    }
}
```

### Trades

Channel name: <mark style="color:red;">**{symbol}@trades**</mark> (e.g. DOGE-PERP\@trades).

#### Example Response

```
{
    "channel": "DOGE-PERP@trades",
    "data": {
        "id": "0x",
        "price": "0.102000",
        "qty": "1234",
        "quoteQty": "125.868000",
        "time": 1725315151174
    }
}
```

## Private WS Endpoints

## Authentication

To establish a connection to private endpoints, the client must obtain *listenKey*. For all methods, include the *X-API-Key* in the header obtained via /register.

### POST /account/listenKey

Returns a listen key that is valid for 60 minutes. If a client has an active listenKey, it will return the existing listenKey and extend its validity by 60 minutes.

#### Parameters

* None

#### Example Response

```json
{
    "listenKey": "579e1280448d4843b190c50fbd170078"
}
```

### PUT /account/listenKey

Extends the expiry of the current listen key by 60 minutes. If the existing key has already expired or there is no listen key, it will return an error response.

#### Parameters

* None

#### Example Response:

```json
{
    "listenKey": "579e1280448d4843b190c50fbd170078"
}
```

#### Example Error Response:

```json
{
    "code": 1125,
    "msg": "Listen key expired. Make a POST request to create a new key."
}
```

### DELETE /account/listenKey

Closes the current listen key.

#### Parameters

* None

#### Example Response

```json
{}
```

## Subscription

Uses the same base url as the public endpoint but the client must pass in an additional query parameter, *listenKey* when sending a request for subscription.

e.g. `wss://ws-prod.hz.vestmarkets.com/ws-api?version=1.0&websocketserver=restserver0&listenKey=e4787535db6e4f12b5570f5a0f17b7ed`

Channel name: <mark style="color:red;">**account\_private**</mark>.

Each response will be in the following format:

```json
{
    "channel": "account_private",
    "data": {
        "event": event_name,
        "args": payload
    }
}
```

### Error Codes

```
INTERNAL_ERROR=1011
SERVICE_RESTART=1012

WRONG_VERSION=4000
ACCOUNT_GROUP_NOT_FOUND=4001 
ACCOUNT_GROUP_INVALID=4002
LISTEN_KEY_REQUIRED=4003
LISTEN_KEY_NOT_FOUND=4004
LISTEN_KEY_EXPIRED=4005
```

### Order

event\_name: <mark style="color:red;">**ORDER**</mark>.

#### Example Payload for New Order

```json
{
    "id": "0x0",
    "symbol": "BTC-PERP",
    "isBuy": true,
    "orderType": "MARKET",
    "limitPrice": "30000.00",
    "size": "0.1000",
    "reduceOnly": false,
    "initMarginRatio": "0.1250",
    "status": "NEW",
    "postTime": 1683849600076,
    "nonce": 0
}
```

#### Example Payload for Order Execution

```json
{
    "id": "0x0",
    "symbol": "BTC-PERP",
    "isBuy": true,
    "orderType": "MARKET",
    "limitPrice": "30000.00",
    "size": "0.1000",
    "reduceOnly": false,
    "initMarginRatio": "0.1250",
    "status": "FILLED",
    "lastFilledSize": "0.1000",
    "lastFilledPrice": "30000.00",
    "lastFilledTime": 1683849600076,
    "avgFilledPrice": "30000.00",
    "cumFunding": "0.100000",
    "fees": "0.010000", // includes premium
    "postTime": 1683849600076,
    "nonce": 0
}
```

#### Example Payload for Order Cancellation

```json
{
    "id": "0x0",
    "status": "CANCELLED",
    "postTime": 1683849600076,
    "nonce": 0
}
```

#### Example Payload for Order Rejection

```json
{
    "id": "0x0",
    "status": "REJECTED",
    "code": 3010,
    "postTime": 1683849600076,
    "nonce": 0
}
```

### LP Order

event\_name: <mark style="color:red;">**LP**</mark>.

#### Example Payload for Order Execution

```json
{
    "id": "0x0",
    "size": "100",
    "orderType": "DEPOSIT",
    "status": "FILLED",
    "code": null,
    "postTime": 1683849600076,
    "nonce": 0
}
```

### Transfer

event\_name: <mark style="color:red;">**TRANSFER**</mark>.

#### Example Payload

```json
{
    "id": "0x0",
    "size": "100",
    "orderType": "DEPOSIT",
    "status": "FILLED",
    "code": null,
    "chainId": 1,
    "postTime": 1683849600076,
    "nonce": 0
}
```