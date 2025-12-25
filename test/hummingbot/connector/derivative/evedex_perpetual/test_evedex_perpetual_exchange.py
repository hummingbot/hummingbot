import asyncio
import sys
import types
from decimal import Decimal
from unittest import TestCase
from unittest.mock import MagicMock

sys.modules.setdefault("pandas", MagicMock())
sys.modules.setdefault("numpy", MagicMock())
sys.modules.setdefault("aiohttp", MagicMock())
sys.modules.setdefault("ujson", MagicMock())
sys.modules.setdefault("cachetools", types.SimpleNamespace(TTLCache=lambda *_, **__: {}))
core_schema_stub = types.SimpleNamespace(
    CoreSchema=object,
    no_info_after_validator_function=lambda *_, **__: None,
    dict_schema=lambda *_, **__: None,
    any_schema=lambda *_, **__: None,
    set_schema=lambda *_, **__: None,
)
sys.modules.setdefault("pydantic_core", types.SimpleNamespace(core_schema=core_schema_stub))
exchange_base_stub = types.SimpleNamespace(ExchangeBase=object)
sys.modules.setdefault("hummingbot.connector.exchange_base", exchange_base_stub)
trading_rule_stub = types.SimpleNamespace(TradingRule=object)
sys.modules.setdefault("hummingbot.connector.trading_rule", trading_rule_stub)
limit_order_stub = types.SimpleNamespace(LimitOrder=object)
sys.modules.setdefault("hummingbot.core.data_type.limit_order", limit_order_stub)
hexbytes_stub = types.SimpleNamespace(HexBytes=bytes)
sys.modules.setdefault("hexbytes", hexbytes_stub)
network_status_stub = types.SimpleNamespace(NetworkStatus=types.SimpleNamespace(CONNECTED="connected", NOT_CONNECTED="not_connected"))
sys.modules.setdefault("hummingbot.core.network_iterator", network_status_stub)
eth_account_stub = types.SimpleNamespace(
    Account=types.SimpleNamespace(from_key=lambda *_args, **_kwargs: types.SimpleNamespace(address="0x0"))
)
sys.modules.setdefault("eth_account", eth_account_stub)
eth_account_messages_stub = types.SimpleNamespace(
    encode_defunct=lambda *_args, **_kwargs: None,
    encode_typed_data=lambda *_args, **_kwargs: None,
)
sys.modules.setdefault("eth_account.messages", eth_account_messages_stub)
class _DummyTimeout:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


async_timeout_stub = types.SimpleNamespace(timeout=lambda *_, **__: _DummyTimeout())
sys.modules.setdefault("async_timeout", async_timeout_stub)

from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_exchange import (
    EvedexPerpetualExchange,
)


class DummyOrder:
    def __init__(self, client_order_id: str, exchange_order_id: str, trading_pair: str):
        self.client_order_id = client_order_id
        self.exchange_order_id = exchange_order_id
        self.trading_pair = trading_pair


class DummyOrderTracker:
    def __init__(self):
        self._orders = {}
        self.process_order_update = MagicMock()
        self.process_trade_update = MagicMock()

    def start_tracking_order(self, order: DummyOrder):
        self._orders[order.client_order_id] = order

    def fetch_order(self, client_order_id: str = None, exchange_order_id: str = None):
        if client_order_id and client_order_id in self._orders:
            return self._orders[client_order_id]
        if exchange_order_id:
            for order in self._orders.values():
                if order.exchange_order_id == exchange_order_id:
                    return order
        return None

    @property
    def all_fillable_orders_by_exchange_order_id(self):
        return {order.exchange_order_id: order for order in self._orders.values()}


class EvedexPerpetualExchangeOrderUpdateTests(TestCase):
    def setUp(self):
        super().setUp()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.exchange = EvedexPerpetualExchange.__new__(EvedexPerpetualExchange)

        self.order_tracker = DummyOrderTracker()
        self.exchange._order_tracker = self.order_tracker
        from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_exchange as exchange_module

        class DummyTradeFeeBase:
            def __init__(self, percent=None, percent_token=None, flat_fees=None):
                self.percent = percent
                self.percent_token = percent_token
                self.flat_fees = flat_fees or []

        exchange_module.TradeFeeBase = DummyTradeFeeBase
        self.exchange._parse_order_status = lambda status: status

        self.tracked_order = DummyOrder(
            client_order_id="CID-123",
            exchange_order_id="EID-456",
            trading_pair="BTC-USD",
        )
        self.order_tracker.start_tracking_order(self.tracked_order)

    def tearDown(self):
        self.loop.close()
        asyncio.set_event_loop(None)

    def test_process_order_update_uses_tracked_client_id(self):
        event = {
            "order_id": "EID-456",
            "client_order_id": "CID-123",
            "trading_pair": "BTC-USD",
            "status": "NEW",
            "timestamp": 1699999999.0,
        }

        self.loop.run_until_complete(self.exchange._process_order_update(event))

        process_call = self.exchange._order_tracker.process_order_update.call_args
        self.assertIsNotNone(process_call)
        order_update = process_call[0][0]
        self.assertEqual("CID-123", order_update.client_order_id)
        self.assertEqual("EID-456", order_update.exchange_order_id)

    def test_process_order_fill_uses_tracked_ids(self):
        event = {
            "order_id": "EID-456",
            "trading_pair": "BTC-USD",
            "price": "21000",
            "quantity": "0.05",
            "timestamp": 1700000000.0,
            "fee": "0.1",
            "fee_currency": "USD",
            "execution_id": "fill-1",
        }

        self.loop.run_until_complete(self.exchange._process_order_fill(event))

        process_call = self.exchange._order_tracker.process_trade_update.call_args
        self.assertIsNotNone(process_call)
        trade_update = process_call[0][0]
        self.assertEqual("CID-123", trade_update.client_order_id)
        self.assertEqual("EID-456", trade_update.exchange_order_id)
        self.assertEqual("BTC-USD", trade_update.trading_pair)
