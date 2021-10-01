# Bamboo Relay


[Bamboo Relay](https://bamboorelay.com/) is an exchange application specializing in ERC-20 tokens that uses the [0x Protocol](https://0x.org/).
Currently, Bamboo Relay allows any user to connect their wallet and trade between any coin pair combination.

## Using the connector

Because Bamboo Relay is a decentralized exchange, you will need an independent cryptocurrency wallet and an ethereum node in order to use Hummingbot. See below for information on how to create these:

- [Creating a crypto wallet](/operation/connect-exchange/#wallets)
- [Creating an ethereum node](/operation/connect-exchange/#setup-ethereum-nodes)

## Connector operating modes

The Bamboo Relay connector supports two modes of operation, [open order book](https://0x.org/wiki#Open-Orderbook) and [coordinated order book](https://github.com/0xProject/0x-protocol-specification/blob/master/v2/coordinator-specification.md).

By default the open order book mode is on for maximum order visibility and network syndication.

### Open order book

Open order book mode allows for off-chain orders to be submitted and any taker to fill these orders on-chain.
Orders may only be cancelled by submitting a transaction and paying gas network costs.

Open orders are syndicated through the [0x Mesh Network](https://0x-org.gitbook.io/mesh/) as well as directly submitted to the [0x API](https://0x.org/docs/api).

### Coordinated order book

The coordinated order book mode extends the open order book mode by adding the ability to soft-cancel orders and a selective delay on order fills, while preserving network and contract fillable liquidity.
This is achieved by the use of a coordinator server component and coordinator smart contracts.

At this time coordinated orders are not supported through the [0x Mesh Network](https://0x-org.gitbook.io/mesh/) or [0x API](https://0x.org/docs/api).

To enable coordinator mode set the `bamboo_relay_use_coordinator` parameter to `true` in `conf_global.yml` in the `/conf` directory.

## Pre-emptive cancels

The Bamboo Relay front-end UI does not show orders that have less than 30 seconds expiry remaining. This is so that users should only attempt to fill orders that have a reasonable chance of succeeding.

When running the connector in coordinated mode it is advised to enable this setting so that orders are automatically refreshed when they have 30 seconds remaining.

## Daily server restarts

Bamboo Relay's server restarts at least twice a day which will drop WebSocket connections. As a result, errors will show up in the logs a few times in a day transiently before Hummingbot just reconnects.

Specifically it is Nginx that restarts that takes ~1 second when it happens. If it ends up being minutes, then there may be a problem. If it's just for a few seconds then it's almost 100% the restarts.

```
2019-09-05 18:15:02,335 - hummingbot.market.bamboo_relay.bamboo_relay_api_order_book_data_source - ERROR - Unexpected error with WebSocket connection. Retrying after 30 seconds...
Traceback (most recent call last):
  File "/hummingbot/market/bamboo_relay/bamboo_relay_api_order_book_data_source.py", line 214, in listen_for_order_book_diffs
    async with websockets.connect(WS_URL) as ws:
  File "/opt/conda/envs/hummingbot/lib/python3.6/site-packages/websockets/py35/client.py", line 2, in __aenter__
    return await self
  File "/opt/conda/envs/hummingbot/lib/python3.6/site-packages/websockets/py35/client.py", line 12, in __await_impl__
    transport, protocol = await self._creating_connection
  File "/opt/conda/envs/hummingbot/lib/python3.6/asyncio/base_events.py", line 809, in create_connection
    sock, protocol_factory, ssl, server_hostname)
  File "/opt/conda/envs/hummingbot/lib/python3.6/asyncio/base_events.py", line 835, in _create_connection_transport
    yield from waiter
  File "/opt/conda/envs/hummingbot/lib/python3.6/asyncio/selector_events.py", line 725, in _read_ready
    data = self._sock.recv(self.max_size)

ConnectionResetError: [Errno 104] Connection reset by peer

raise OSError(err, 'Connect call failed %s' % (address,))
ConnectionRefusedError: [Errno 111] Connect call failed ('188.166.94.193', 443)

raise InvalidStatusCode(status_code)
websockets.exceptions.InvalidStatusCode: Status code not 101: 502
```

## Miscellaneous info

### Minimum order sizes

The minimum acceptable order size is 0.004 WETH for pairs traded against WETH, this is to prevent transactional costs being higher than the nominal order amount.

### Transaction fees

Currently Bamboo Relay does not charge trading or withdrawal fees. This is set to change February 1st, 2020 with the introduction of relayer fees. See the [fee schedule](https://bamboorelay.com/fees) for the latest information.

0x Protocol V3 levies an additional protocol fee for each order filled, this is calculated as 150,000 \* gasPrice per order.
This is in addition to the standard Ethereum transaction fees.

## Contact

This connector is maintained by [Bamboo Relay](https://bamboorelay.com), which can be contacted at:

- [dex@bamboorelay.com](mailto:dex@bamboorelay.com)
- [Twitter](https://twitter.com/bamboorelay) | [Telegram](https://t.me/bamboorelay) | [Discord](https://discord.gg/6tMFa5E)
