import asyncio
import contextlib
import unittest
from decimal import Decimal
from typing import List, Optional
from unittest.mock import patch

from aiounittest import async_test

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.amm_lp.gateway_in_flight_lp_order import GatewayInFlightLPOrder
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeSchema
from hummingbot.core.event.events import LPType
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.strategy.amm_v3_lp.amm_v3_lp import AmmV3LpStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

TRADING_PAIR: str = "HBOT-USDT"
BASE_ASSET: str = TRADING_PAIR.split("-")[0]
QUOTE_ASSET: str = TRADING_PAIR.split("-")[1]

ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
s_decimal_0 = Decimal(0)


class MockAMMLP(ConnectorBase):
    def __init__(self, name):
        self._name = name
        super().__init__(ClientConfigAdapter(ClientConfigMap()))
        self._pool_price = {}
        self._in_flight_orders = {}
        self._network_transaction_fee = TokenAmount("ETH", s_decimal_0)

    @property
    def name(self):
        return self._name

    @property
    def network_transaction_fee(self) -> TokenAmount:
        return self._network_transaction_fee

    @network_transaction_fee.setter
    def network_transaction_fee(self, fee: TokenAmount):
        self._network_transaction_fee = fee

    @property
    def connector_name(self):
        return "uniswapLP"

    @staticmethod
    def is_approval_order(in_flight_order: GatewayInFlightLPOrder) -> bool:
        return False

    @property
    def amm_lp_orders(self):
        return [
            in_flight_order
            for in_flight_order in self._in_flight_orders.values()
            if not self.is_approval_order(in_flight_order)
            and not in_flight_order.is_pending_cancel_confirmation
        ]

    async def get_price(self, trading_pair: str, fee: str) -> Decimal:
        return self._pool_price[trading_pair]

    def set_price(self, trading_pair, price):
        self._pool_price[trading_pair] = [Decimal(str(price))]

    def set_balance(self, token, balance):
        self._account_balances[token] = Decimal(str(balance))
        self._account_available_balances[token] = Decimal(str(balance))

    def add_liquidity(self, trading_pair: str, amount_0: Decimal, amount_1: Decimal, lower_price: Decimal, upper_price: Decimal, fee: str, **request_args) -> str:
        order_id = f"add-{trading_pair}-{get_tracking_nonce()}"
        self._in_flight_orders[order_id] = GatewayInFlightLPOrder(client_order_id=order_id,
                                                                  exchange_order_id="",
                                                                  trading_pair=trading_pair,
                                                                  lp_type=LPType.ADD,
                                                                  lower_price=lower_price,
                                                                  upper_price=upper_price,
                                                                  amount_0=amount_0,
                                                                  amount_1=amount_1,
                                                                  token_id=1234,
                                                                  creation_timestamp=self.current_timestamp,
                                                                  gas_price=Decimal("1"))
        self._in_flight_orders[order_id].current_state = OrderState.CREATED
        return order_id

    def remove_liquidity(self, trading_pair: str, token_id: int, reduce_percent: Optional[int] = 100, **request_args) -> str:
        order_id = f"remove-{trading_pair}-{get_tracking_nonce()}"
        self._in_flight_orders[order_id] = GatewayInFlightLPOrder(client_order_id=order_id,
                                                                  exchange_order_id="",
                                                                  trading_pair=trading_pair,
                                                                  lp_type=LPType.REMOVE,
                                                                  lower_price=s_decimal_0,
                                                                  upper_price=s_decimal_0,
                                                                  amount_0=s_decimal_0,
                                                                  amount_1=s_decimal_0,
                                                                  token_id=1234,
                                                                  creation_timestamp=self.current_timestamp,
                                                                  gas_price=Decimal("1"))
        return order_id

    def collect_fees(self, trading_pair: str, token_id: int, **request_args) -> str:
        order_id = f"collect-{trading_pair}-{get_tracking_nonce()}"
        self._in_flight_orders[order_id] = GatewayInFlightLPOrder(client_order_id=order_id,
                                                                  exchange_order_id="",
                                                                  trading_pair=trading_pair,
                                                                  lp_type=LPType.COLLECT,
                                                                  lower_price=s_decimal_0,
                                                                  upper_price=s_decimal_0,
                                                                  amount_0=s_decimal_0,
                                                                  amount_1=s_decimal_0,
                                                                  token_id=1234,
                                                                  creation_timestamp=self.current_timestamp,
                                                                  gas_price=Decimal("1"))
        return order_id

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("0.01")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal("0.01")

    def ready(self):
        return True

    async def check_network(self) -> NetworkStatus:
        return NetworkStatus.CONNECTED

    async def cancel_outdated_orders(self, _: int) -> List:
        return []


class AmmV3LpUnitTest(unittest.TestCase):
    def setUp(self):
        self.clock: Clock = Clock(ClockMode.REALTIME)
        self.stack: contextlib.ExitStack = contextlib.ExitStack()
        self.lp: MockAMMLP = MockAMMLP("onion")
        self.lp.set_balance(BASE_ASSET, 500)
        self.lp.set_balance(QUOTE_ASSET, 500)
        self.market_info = MarketTradingPairTuple(self.lp, TRADING_PAIR, BASE_ASSET, QUOTE_ASSET)

        # Set some default price.
        self.lp.set_price(TRADING_PAIR, 1)

        self.strategy = AmmV3LpStrategy(
            self.market_info,
            "LOW",
            Decimal("0.2"),
            Decimal("1"),
            Decimal("10"),
        )
        self.clock.add_iterator(self.lp)
        self.clock.add_iterator(self.strategy)

        self.stack.enter_context(self.clock)
        self.stack.enter_context(patch(
            "hummingbot.client.config.trade_fee_schema_loader.TradeFeeSchemaLoader.configured_schema_for_exchange",
            return_value=TradeFeeSchema()
        ))
        self.clock_task: asyncio.Task = safe_ensure_future(self.clock.run())

    def tearDown(self) -> None:
        self.stack.close()
        self.clock_task.cancel()
        try:
            ev_loop.run_until_complete(self.clock_task)
        except asyncio.CancelledError:
            pass

    @async_test(loop=ev_loop)
    async def test_propose_position_boundary(self):
        lower_price, upper_price = await self.strategy.propose_position_boundary()
        self.assertEqual(lower_price, Decimal("0.9"))
        self.assertEqual(upper_price, Decimal("1.1"))

    @async_test(loop=ev_loop)
    async def test_format_status(self):
        self.lp.set_price(TRADING_PAIR, 0)
        await asyncio.sleep(2)
        expected_status = """  Markets:
    Exchange    Market Pool Price
       onion HBOT-USDT       0E-8

  No active positions.

  Assets:
      Exchange Asset  Total Balance  Available Balance
    0    onion  HBOT            500                500
    1    onion  USDT            500                500"""
        current_status = await self.strategy.format_status()
        print(current_status)
        self.assertTrue(expected_status in current_status)

    @async_test(loop=ev_loop)
    async def test_any_active_position(self):
        await asyncio.sleep(2)
        self.assertTrue(self.strategy.any_active_position(Decimal("1")))

    @async_test(loop=ev_loop)
    async def test_positions_are_created_with_price(self):
        await asyncio.sleep(2)
        self.assertEqual(len(self.strategy.active_positions), 1)
        self.lp.set_price(TRADING_PAIR, 2)
        await asyncio.sleep(2)
        self.assertEqual(len(self.strategy.active_positions), 2)
        self.lp.set_price(TRADING_PAIR, 3)
        await asyncio.sleep(2)
        self.assertEqual(len(self.strategy.active_positions), 3)
        self.lp.set_price(TRADING_PAIR, 2)  # price falls back
        await asyncio.sleep(2)
        self.assertEqual(len(self.strategy.active_positions), 3)  # no new position created when there's an active position
