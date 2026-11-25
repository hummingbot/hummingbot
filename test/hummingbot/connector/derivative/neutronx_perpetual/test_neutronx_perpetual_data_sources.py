import asyncio
from dataclasses import replace
from decimal import Decimal
from test.hummingbot.connector.derivative.neutronx_perpetual.fixtures import (
    ACCOUNT,
    INDEXER_URL,
    NETWORK,
    PRIVATE_KEY,
    FakeDataSource,
    chain_order,
    chain_position,
    frame,
    orderbook_params,
)
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from neutronx_sdk import NeutronXError, PrivateKey
from neutronx_sdk.models import AgentKey, Coin
from neutronx_sdk.node import PositionsPage
from neutronx_sdk.orders import AGENT_KEY_MSG_TYPE_URLS

from hummingbot.connector.derivative.neutronx_perpetual.data_sources import indexer_stream
from hummingbot.connector.derivative.neutronx_perpetual.data_sources.neutronx_data_source import (
    NeutronxDataSource,
    build_wallet,
)
from hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_api_order_book_data_source import (
    NeutronxPerpetualAPIOrderBookDataSource,
)
from hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_derivative import NeutronxPerpetualDerivative
from hummingbot.connector.derivative.neutronx_perpetual.neutronx_perpetual_user_stream_data_source import (
    NeutronxPerpetualUserStreamDataSource,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessageType

PAIR = "BTC-USDC"
BOOK = {"pair": "BTCUSDC", "bids": [{"price": "65000", "quantity": "1"}], "asks": [{"price": "65010", "quantity": "2"}]}
TICKER = {"pair": "BTCUSDC", "last_price": "65005", "mark_price": "65004", "funding_rate": "0.0001",
          "next_funding_at": "2026-11-10T13:00:00+00:00"}


class FakeWebSocket:
    def __init__(self, messages: List[Any]) -> None:
        self.sent: List[Any] = []
        self._messages = messages

    async def send(self, request: Any) -> None:
        self.sent.append(request.payload)

    async def disconnect(self) -> None:
        self.closed = True

    async def iter_messages(self):
        for message in self._messages:
            yield SimpleNamespace(data=message)


class OrderBookDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.connector = NeutronxPerpetualDerivative(
            neutronx_perpetual_account_address=ACCOUNT,
            trading_pairs=[PAIR],
            network=NETWORK,
            data_source=FakeDataSource(),
        )
        await self.connector._update_trading_rules()
        self.source = NeutronxPerpetualAPIOrderBookDataSource([PAIR], self.connector, self.connector._web_assistants_factory)

    def test_channel_routing(self):
        self.assertEqual(self.source._snapshot_messages_queue_key, self.source._channel_originating_message(frame("orderbook", BOOK)))
        self.assertEqual(self.source._trade_messages_queue_key, self.source._channel_originating_message(frame("trades", [], "update")))
        self.assertEqual("", self.source._channel_originating_message(frame("trades", [], "snapshot")))
        self.assertEqual(self.source._funding_info_messages_queue_key, self.source._channel_originating_message(frame("ticker", TICKER)))
        self.assertEqual("", self.source._channel_originating_message({"type": "pong"}))
        with self.assertLogs(level="WARNING") as logs:
            refused = self.source._channel_originating_message(
                {"type": "error", "code": "TOO_MANY_SUBSCRIPTIONS", "message": "max 50"}
            )
        self.assertEqual("", refused)
        self.assertIn("TOO_MANY_SUBSCRIPTIONS", logs.output[0])

    async def test_parsers(self):
        queue: asyncio.Queue = asyncio.Queue()
        await self.source._parse_order_book_snapshot_message(frame("orderbook", BOOK), queue)
        await self.source._parse_order_book_snapshot_message(frame("orderbook", BOOK), queue)
        first, second = queue.get_nowait(), queue.get_nowait()
        self.assertIs(OrderBookMessageType.SNAPSHOT, first.type)
        self.assertGreater(second.update_id, first.update_id)
        trade = {"id": "9:1", "pair": "BTCUSDC", "price": "65020", "quantity": "0.1", "block_height": 9,
                 "time": "2026-11-10T12:00:00+00:00", "taker_side": "SELL"}
        await self.source._parse_trade_message(frame("trades", [trade, {**trade, "pair": "ZZZUSDC"}], "update"), queue)
        message = queue.get_nowait()
        self.assertEqual(float(TradeType.SELL.value), message.content["trade_type"])
        self.assertTrue(queue.empty())
        await self.source._parse_funding_info_message(frame("ticker", TICKER), queue)
        self.assertEqual(Decimal("0.0001"), queue.get_nowait().rate)

    async def test_rest_snapshot_funding_and_prices(self):
        with aioresponses() as mock:
            mock.get(f"{INDEXER_URL}/markets/BTCUSDC/orderbook?depth=100", payload=BOOK)
            mock.get(f"{INDEXER_URL}/markets/tickers", payload=[TICKER, {"pair": "ETHUSDC"}], repeat=True)
            snapshot = await self.source._order_book_snapshot(PAIR)
            funding = await self.source.get_funding_info(PAIR)
            prices = await self.source.get_last_traded_prices([PAIR, "ETH-USDC", "SOL-USDC"])
            with self.assertRaises(IOError):
                await self.source.get_funding_info("SOL-USDC")
        self.assertEqual(65000.0, snapshot.bids[0].price)
        self.assertEqual(Decimal(65004), funding.mark_price)
        self.assertEqual({PAIR: 65005.0}, prices)

    async def test_subscriptions_are_grouped_under_the_socket_cap(self):
        sockets: List[FakeWebSocket] = []

        async def connect(api_factory, network, api_key=None):
            ws = FakeWebSocket([])
            sockets.append(ws)
            return ws

        pairs = [f"P{i}-USDC" for i in range(17)]
        self.source._trading_pairs = pairs
        with patch.object(indexer_stream, "connect", side_effect=connect), \
                patch.object(NeutronxPerpetualAPIOrderBookDataSource, "_process_websocket_messages",
                             new=AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):
                await self.source.listen_for_subscriptions()
        self.assertEqual([50, 1], [len(group) for group in self.source._groups])
        self.assertEqual(51, sum(len(ws.sent) for ws in sockets))
        self.assertTrue(all(len(ws.sent) <= self.connector.max_subscriptions for ws in sockets))

    async def test_market_data_alone_initializes_the_symbol_map(self):
        connector = NeutronxPerpetualDerivative(
            neutronx_perpetual_account_address=ACCOUNT,
            trading_pairs=[PAIR],
            trading_required=False,
            network=NETWORK,
            data_source=FakeDataSource(),
        )
        source = NeutronxPerpetualAPIOrderBookDataSource([PAIR], connector, connector._web_assistants_factory)
        self.assertIsNone(connector.trading_pair_for_indexer("BTCUSDC"))
        with aioresponses() as mock:
            mock.get(f"{INDEXER_URL}/markets/BTCUSDC/orderbook?depth=100", payload=BOOK)
            await source._order_book_snapshot(PAIR)
        self.assertEqual(PAIR, connector.trading_pair_for_indexer("BTCUSDC"))
        self.assertTrue(connector.trading_pair_symbol_map_ready())

    async def test_dynamic_subscriptions_fill_free_groups(self):
        ws = FakeWebSocket([])
        self.source._groups = [[("orderbook", "BTC/USDC")]]
        self.source._sockets = {0: ws}
        self.assertTrue(await self.source.subscribe_to_trading_pair("ETH-USDC"))
        self.assertEqual(4, len(self.source._groups[0]))
        self.assertEqual(["subscribe"] * 3, [p["type"] for p in ws.sent])
        self.assertTrue(await self.source.unsubscribe_from_trading_pair("ETH-USDC"))
        self.assertEqual([("orderbook", "BTC/USDC")], self.source._groups[0])
        self.assertEqual(["unsubscribe"] * 3, [p["type"] for p in ws.sent[3:]])
        self.source._groups = [[("x", str(i)) for i in range(49)]]
        with patch.object(self.source, "_listen_group", new=AsyncMock()) as listen:
            self.assertTrue(await self.source.subscribe_to_trading_pair("SOL-USDC"))
            await asyncio.sleep(0)
        self.assertEqual(2, len(self.source._groups))
        listen.assert_awaited_once_with(1)

    async def test_group_listener_reconnects_after_errors(self):
        calls = []

        async def connect(api_factory, network, api_key=None):
            calls.append(api_key)
            if len(calls) == 1:
                raise RuntimeError("refused")
            if len(calls) == 2:
                raise ConnectionError("closed")
            raise asyncio.CancelledError

        self.source._groups = [[("orderbook", "BTC/USDC")]]
        with patch.object(indexer_stream, "connect", side_effect=connect), \
                patch.object(self.source, "_sleep", new=AsyncMock()):
            with self.assertRaises(asyncio.CancelledError):
                await self.source._listen_group(0)
        self.assertEqual(3, len(calls))
        self.assertEqual({}, self.source._sockets)


class UserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.connector = NeutronxPerpetualDerivative(
            neutronx_perpetual_account_address=ACCOUNT, network=NETWORK, data_source=FakeDataSource()
        )
        self.source = NeutronxPerpetualUserStreamDataSource(self.connector, self.connector._web_assistants_factory)

    async def test_subscribes_owner_channels_and_pings(self):
        ws = FakeWebSocket([])
        await self.source._subscribe_channels(ws)
        await self.source._send_ping(ws)
        self.assertEqual([("orders", ACCOUNT), ("fills", ACCOUNT), ("positions", ACCOUNT)],
                         [(p["channel"], p["id"]) for p in ws.sent[:3]])
        self.assertEqual({"type": "ping"}, ws.sent[3])

    async def test_forwards_only_owner_data_frames(self):
        ws = FakeWebSocket([{"type": "subscribed", "channel": "fills"}, frame("fills", []), frame("ticker", {}), "raw"])
        queue: asyncio.Queue = asyncio.Queue()
        await self.source._process_websocket_messages(ws, queue)
        self.assertEqual("fills", queue.get_nowait()["channel"])
        self.assertTrue(queue.empty())
        refused = FakeWebSocket([{"type": "error", "code": "NOT_A_TRADER", "message": "no"}, frame("orders", [])])
        with self.assertLogs(level="WARNING"):
            await self.source._process_websocket_messages(refused, queue)
        self.assertEqual("orders", queue.get_nowait()["channel"])


def _client(enabled: bool = True, key: Any = None, fee_balance: int = 1_000_000) -> MagicMock:
    client = MagicMock()
    client.network = NETWORK
    client.orderbook.params = AsyncMock(return_value=orderbook_params(rate_limit=20))
    client.orderbook.all_user_orders = AsyncMock(
        return_value=(chain_order(1, client_id=4_000_000_000), replace(chain_order(2, client_id=7), subaccount_id=1))
    )
    client.orderbook.order = AsyncMock(return_value=None)
    client.orderbook.fee_tier = AsyncMock()
    client.perps.params = AsyncMock(return_value=SimpleNamespace(margin_denom="ibc/MARGIN"))
    client.perps.markets = AsyncMock(return_value=())
    client.perps.subaccount_balance = AsyncMock()
    client.perps.positions = AsyncMock(
        side_effect=[
            PositionsPage(positions=(chain_position(),), has_next=True),
            PositionsPage(positions=(chain_position("ETH/USDC"),), has_next=False),
        ]
    )
    client.orderbook.all_user_orders.side_effect = None
    client.agentkeys.enabled = AsyncMock(return_value=enabled)
    client.agentkeys.agent_key = AsyncMock(return_value=key)
    client.node.status = AsyncMock(return_value=SimpleNamespace(height=77))
    client.bank.balances = AsyncMock(
        return_value=(Coin(denom="untx", amount=5), Coin(denom="ibc/MARGIN", amount=fee_balance))
    )
    client.close = AsyncMock()
    return client


class NeutronxDataSourceTests(IsolatedAsyncioWrapperTestCase):
    def test_build_wallet_for_own_and_agent_keys(self):
        own = build_wallet(NETWORK, ACCOUNT, PRIVATE_KEY, 0)
        self.assertEqual(ACCOUNT, own.address)
        self.assertFalse(own.is_agent)
        agent_key = PrivateKey.from_hex("22" * 32)
        agent = build_wallet(NETWORK, ACCOUNT, "22" * 32, 3)
        self.assertEqual((ACCOUNT, 3), (agent.address, agent.agent_key_id))
        self.assertNotEqual(agent_key.public_key.address(NETWORK.bech32_prefix), agent.address)
        with self.assertRaises(ValueError):
            build_wallet(NETWORK, ACCOUNT, "22" * 32, 0)

    async def test_start_trading_with_own_key(self):
        client = _client()
        source = NeutronxDataSource(NETWORK, ACCOUNT, wallet=build_wallet(NETWORK, ACCOUNT, PRIVATE_KEY, 0), client=client)
        await source.start_trading()
        self.assertTrue(source.trading_ready)
        self.assertIn(4_000_000_000, source.client_ids)
        self.assertEqual("ibc/MARGIN", source._sender.fee.denom)
        self.assertEqual(Decimal("0.001"), source._sender.fee.gas_price)
        self.assertEqual(20, source._queue._max_places)
        self.assertEqual(77, await source.check_node())
        self.assertEqual(("BTC/USDC", "ETH/USDC"), tuple(p.pair for p in await source.positions()))
        self.assertEqual(1, len(await source.open_orders()))
        await source.close()
        client.close.assert_awaited_once()
        self.assertFalse(source.trading_ready)

    async def test_start_trading_warns_when_the_wallet_is_short_of_fees(self):
        wallet = build_wallet(NETWORK, ACCOUNT, PRIVATE_KEY, 0)
        funded = NeutronxDataSource(NETWORK, ACCOUNT, wallet=wallet, client=_client())
        with patch.object(NeutronxDataSource, "logger") as logger:
            await funded.start_trading()
            logger.return_value.warning.assert_not_called()
            short = NeutronxDataSource(NETWORK, ACCOUNT, wallet=wallet, client=_client(fee_balance=99_999))
            await short.start_trading()
            message = logger.return_value.warning.call_args.args[0]
        self.assertIn("holds 0.099999 USDC for transaction fees", message)
        self.assertTrue(short.trading_ready)
        await funded.stop()
        await short.stop()

    async def test_overlapping_starts_leave_one_running_queue(self):
        source = NeutronxDataSource(NETWORK, ACCOUNT, wallet=build_wallet(NETWORK, ACCOUNT, PRIVATE_KEY, 0), client=_client())
        await asyncio.gather(source.start_trading(), source.start_trading())
        first = source._queue
        self.assertTrue(first.running)
        await source.start_trading()
        self.assertFalse(first.running)
        self.assertTrue(source._queue.running)
        await source.stop()
        self.assertFalse(source.trading_ready)

    async def test_agent_key_problems_stop_trading(self):
        wallet = build_wallet(NETWORK, ACCOUNT, "22" * 32, 3)
        with self.assertRaises(NeutronXError):
            await NeutronxDataSource(NETWORK, ACCOUNT, wallet=wallet, client=_client(enabled=False)).start_trading()
        live = AgentKey(
            account=ACCOUNT,
            key_id=3,
            name="bot",
            pubkey=wallet.public_key.compressed,
            expires_at=4_000_000_000,
            created_block=1,
            msg_type_urls=AGENT_KEY_MSG_TYPE_URLS,
            pairs=(),
            subaccount_ids=(),
        )
        source = NeutronxDataSource(NETWORK, ACCOUNT, wallet=wallet, client=_client(key=live))
        await source.start_trading()
        self.assertTrue(source.trading_ready)
        await source.stop()

    async def test_trading_needs_a_key_and_a_start(self):
        source = NeutronxDataSource(NETWORK, ACCOUNT, client=_client())
        with self.assertRaises(NeutronXError):
            await source.start_trading()
        with self.assertRaises(ConnectionError):
            await source.cancel(1)
        self.assertIsNone(await source.order(1))
        self.assertIs(source.client, source._client)
