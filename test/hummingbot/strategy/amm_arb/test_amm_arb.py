import asyncio
import contextlib
import unittest
from decimal import Decimal
from typing import List
from unittest.mock import patch

from aiounittest import async_test

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.data_type.trade_fee import TokenAmount, TradeFeeSchema
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    MarketEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.utils.fixed_rate_source import FixedRateSource
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

TRADING_PAIR: str = "HBOT-USDT"
BASE_ASSET: str = TRADING_PAIR.split("-")[0]
QUOTE_ASSET: str = TRADING_PAIR.split("-")[1]

ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
s_decimal_0 = Decimal(0)


class MockAMM(ConnectorBase):
    def __init__(self, name, client_config_map: "ClientConfigAdapter"):
        self._name = name
        super().__init__(client_config_map)
        self._buy_prices = {}
        self._sell_prices = {}
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
        return "uniswap_ethereum_mainnet"

    @property
    def status_dict(self):
        return {"Balance": False}

    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        if is_buy:
            return self._buy_prices[trading_pair]
        else:
            return self._sell_prices[trading_pair]

    async def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        return await self.get_quote_price(trading_pair, is_buy, amount)

    def set_prices(self, trading_pair, is_buy, price):
        if is_buy:
            self._buy_prices[trading_pair] = Decimal(str(price))
        else:
            self._sell_prices[trading_pair] = Decimal(str(price))

    def set_balance(self, token, balance):
        self._account_balances[token] = Decimal(str(balance))
        self._account_available_balances[token] = Decimal(str(balance))

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs):
        return self.place_order(True, trading_pair, amount, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs):
        return self.place_order(False, trading_pair, amount, price)

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal):
        side = "buy" if is_buy else "sell"
        order_id = f"{side}-{trading_pair}-{get_tracking_nonce()}"
        event_tag = MarketEvent.BuyOrderCreated if is_buy else MarketEvent.SellOrderCreated
        event_class = BuyOrderCreatedEvent if is_buy else SellOrderCreatedEvent
        self.trigger_event(event_tag,
                           event_class(
                               self.current_timestamp,
                               OrderType.LIMIT,
                               trading_pair,
                               amount,
                               price,
                               order_id,
                               self.current_timestamp))
        return order_id

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("0.01")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal("0.01")

    def estimate_fee_pct(self, is_maker: bool):
        return Decimal("0")

    def ready(self):
        return True

    async def check_network(self) -> NetworkStatus:
        return NetworkStatus.CONNECTED

    async def cancel_outdated_orders(self, _: int) -> List:
        return []


class AmmArbUnitTest(unittest.TestCase):
    def setUp(self):
        self.clock: Clock = Clock(ClockMode.REALTIME)
        self.stack: contextlib.ExitStack = contextlib.ExitStack()
        self.amm_1: MockAMM = MockAMM(
            name="onion",
            client_config_map=ClientConfigAdapter(ClientConfigMap()))
        self.amm_1.set_balance(BASE_ASSET, 500)
        self.amm_1.set_balance(QUOTE_ASSET, 500)
        self.market_info_1 = MarketTradingPairTuple(self.amm_1, TRADING_PAIR, BASE_ASSET, QUOTE_ASSET)

        self.amm_2: MockAMM = MockAMM(
            name="garlic",
            client_config_map=ClientConfigAdapter(ClientConfigMap()))
        self.amm_2.set_balance(BASE_ASSET, 500)
        self.amm_2.set_balance(QUOTE_ASSET, 500)
        self.market_info_2 = MarketTradingPairTuple(self.amm_2, TRADING_PAIR, BASE_ASSET, QUOTE_ASSET)

        # Set some default prices.
        self.amm_1.set_prices(TRADING_PAIR, True, 101)
        self.amm_1.set_prices(TRADING_PAIR, False, 100)
        self.amm_2.set_prices(TRADING_PAIR, True, 105)
        self.amm_2.set_prices(TRADING_PAIR, False, 104)

        self.strategy = AmmArbStrategy()
        self.strategy.init_params(
            self.market_info_1,
            self.market_info_2,
            min_profitability=Decimal("0.01"),
            order_amount=Decimal("1"),
            market_1_slippage_buffer=Decimal("0.001"),
            market_2_slippage_buffer=Decimal("0.002"),
        )
        self.rate_source: FixedRateSource = FixedRateSource()
        self.strategy.rate_source = self.rate_source
        self.clock.add_iterator(self.amm_1)
        self.clock.add_iterator(self.amm_2)
        self.clock.add_iterator(self.strategy)
        self.market_order_fill_logger: EventLogger = EventLogger()
        self.amm_1.add_listener(MarketEvent.OrderFilled, self.market_order_fill_logger)
        self.amm_2.add_listener(MarketEvent.OrderFilled, self.market_order_fill_logger)
        self.rate_source.add_rate("ETH-USDT", Decimal(3000))

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
    async def test_arbitrage_not_profitable(self):
        self.amm_1.set_prices(TRADING_PAIR, True, 101)
        self.amm_1.set_prices(TRADING_PAIR, False, 100)
        self.amm_2.set_prices(TRADING_PAIR, True, 101)
        self.amm_2.set_prices(TRADING_PAIR, False, 100)
        await asyncio.sleep(2)
        taker_orders = self.strategy.tracked_limit_orders + self.strategy.tracked_market_orders
        self.assertTrue(len(taker_orders) == 0)

    @async_test(loop=ev_loop)
    async def test_arb_buy_amm_1_sell_amm_2(self):
        self.amm_1.set_prices(TRADING_PAIR, True, 101)
        self.amm_1.set_prices(TRADING_PAIR, False, 100)
        self.amm_2.set_prices(TRADING_PAIR, True, 105)
        self.amm_2.set_prices(TRADING_PAIR, False, 104)
        await asyncio.sleep(1.5)
        placed_orders = self.strategy.tracked_limit_orders
        amm_1_order = [order for market, order in placed_orders if market == self.amm_1][0]
        amm_2_order = [order for market, order in placed_orders if market == self.amm_2][0]

        self.assertTrue(len(placed_orders) == 2)
        # Check if the order is created as intended
        self.assertEqual(Decimal("1"), amm_1_order.quantity)
        self.assertEqual(True, amm_1_order.is_buy)
        # The order price has to account for slippage_buffer
        exp_price = self.amm_1.quantize_order_price(TRADING_PAIR, Decimal("101") * Decimal("1.001"))
        self.assertEqual(exp_price, amm_1_order.price)
        self.assertEqual(TRADING_PAIR, amm_1_order.trading_pair)

        self.assertEqual(Decimal("1"), amm_2_order.quantity)
        self.assertEqual(False, amm_2_order.is_buy)
        exp_price = self.amm_1.quantize_order_price(TRADING_PAIR, Decimal("104") * (Decimal("1") - Decimal("0.002")))
        self.assertEqual(exp_price, amm_2_order.price)
        self.assertEqual(TRADING_PAIR, amm_2_order.trading_pair)

        # There are outstanding orders, the strategy is not ready to take on new arb
        self.assertFalse(self.strategy.ready_for_new_arb_trades())
        await asyncio.sleep(2)
        placed_orders = self.strategy.tracked_limit_orders
        new_amm_1_order = [order for market, order in placed_orders if market == self.amm_1][0]
        new_amm_2_order = [order for market, order in placed_orders if market == self.amm_2][0]
        # Check if orders remain the same
        self.assertEqual(amm_1_order.client_order_id, new_amm_1_order.client_order_id)
        self.assertEqual(amm_2_order.client_order_id, new_amm_2_order.client_order_id)

    @async_test(loop=ev_loop)
    async def test_arb_buy_amm_2_sell_amm_1(self):
        self.amm_1.set_prices(TRADING_PAIR, True, 105)
        self.amm_1.set_prices(TRADING_PAIR, False, 104)
        self.amm_2.set_prices(TRADING_PAIR, True, 101)
        self.amm_2.set_prices(TRADING_PAIR, False, 100)
        await asyncio.sleep(1.5)
        placed_orders = self.strategy.tracked_limit_orders
        amm_1_order = [order for market, order in placed_orders if market == self.amm_1][0]
        amm_2_order = [order for market, order in placed_orders if market == self.amm_2][0]

        self.assertTrue(len(placed_orders) == 2)
        self.assertEqual(Decimal("1"), amm_1_order.quantity)
        self.assertEqual(False, amm_1_order.is_buy)
        exp_price = self.amm_1.quantize_order_price(TRADING_PAIR, Decimal("104") * (Decimal("1") - Decimal("0.001")))
        self.assertEqual(exp_price, amm_1_order.price)
        self.assertEqual(TRADING_PAIR, amm_1_order.trading_pair)
        self.assertEqual(Decimal("1"), amm_2_order.quantity)
        self.assertEqual(True, amm_2_order.is_buy)
        exp_price = self.amm_1.quantize_order_price(TRADING_PAIR, Decimal("101") * (Decimal("1") + Decimal("0.002")))
        self.assertEqual(exp_price, amm_2_order.price)
        self.assertEqual(TRADING_PAIR, amm_2_order.trading_pair)

    @async_test(loop=ev_loop)
    async def test_insufficient_balance(self):
        self.amm_1.set_prices(TRADING_PAIR, True, 105)
        self.amm_1.set_prices(TRADING_PAIR, False, 104)
        self.amm_2.set_prices(TRADING_PAIR, True, 101)
        self.amm_2.set_prices(TRADING_PAIR, False, 100)
        # set base_asset to below order_amount, so not enough to sell on amm_1
        self.amm_1.set_balance(BASE_ASSET, 0.5)
        await asyncio.sleep(1.5)
        placed_orders = self.strategy.tracked_limit_orders
        self.assertTrue(len(placed_orders) == 0)
        self.amm_1.set_balance(BASE_ASSET, 10)
        # set quote balance to 0 on amm_2, so not enough to buy
        self.amm_2.set_balance(QUOTE_ASSET, 0)
        await asyncio.sleep(1.5)
        placed_orders = self.strategy.tracked_limit_orders
        self.assertTrue(len(placed_orders) == 0)

    @staticmethod
    def trigger_order_complete(is_buy: bool, connector: ConnectorBase, amount: Decimal, price: Decimal,
                               order_id: str):
        # This function triggers order complete event for our mock connector, this is to simulate scenarios more
        # precisely taker orders are fully filled.
        event_tag = MarketEvent.BuyOrderCompleted if is_buy else MarketEvent.SellOrderCompleted
        event_class = BuyOrderCompletedEvent if is_buy else SellOrderCompletedEvent
        connector.trigger_event(event_tag,
                                event_class(connector.current_timestamp, order_id, BASE_ASSET, QUOTE_ASSET,
                                            amount, amount * price, OrderType.LIMIT))

    @async_test(loop=ev_loop)
    async def test_non_concurrent_orders_submission(self):
        # On non concurrent orders submission, the second leg of the arb trade has to wait for the first leg order gets
        # filled.
        self.strategy = AmmArbStrategy()
        self.strategy.init_params(
            self.market_info_1,
            self.market_info_2,
            min_profitability=Decimal("0.01"),
            order_amount=Decimal("1"),
            concurrent_orders_submission=False
        )
        self.strategy.rate_source = self.rate_source
        self.clock.add_iterator(self.strategy)
        await asyncio.sleep(1.5)
        placed_orders = self.strategy.tracked_limit_orders
        self.assertEqual(1, len(placed_orders))
        # Only one order submitted at this point, the one from amm_1
        amm_1_order = [order for market, order in placed_orders if market == self.amm_1][0]
        amm_2_orders = [order for market, order in placed_orders if market == self.amm_2]
        self.assertEqual(0, len(amm_2_orders))
        self.assertEqual(True, amm_1_order.is_buy)
        self.trigger_order_complete(True, self.amm_1, amm_1_order.quantity, amm_1_order.price,
                                    amm_1_order.client_order_id)
        # After the first leg order completed, the second one is now submitted.
        await asyncio.sleep(1.5)
        placed_orders = self.strategy.tracked_limit_orders
        amm_2_orders = [order for market, order in placed_orders if market == self.amm_2]
        self.assertEqual(1, len(amm_2_orders))
        amm_2_order = amm_2_orders[0]
        self.assertEqual(False, amm_2_order.is_buy)
        self.trigger_order_complete(False, self.amm_2, amm_2_order.quantity, amm_2_order.price,
                                    amm_2_order.client_order_id)
        await asyncio.sleep(1.5)
        placed_orders = self.strategy.tracked_limit_orders
        new_amm_1_order = [order for market, order in placed_orders if market == self.amm_1][0]
        # Check if new order is submitted when arb opportunity still presents
        self.assertNotEqual(amm_1_order.client_order_id, new_amm_1_order.client_order_id)

    @async_test(loop=ev_loop)
    async def test_arb_not_profitable_from_gas_prices(self):
        self.amm_1.set_prices(TRADING_PAIR, True, 101)
        self.amm_1.set_prices(TRADING_PAIR, False, 100)
        self.amm_2.set_prices(TRADING_PAIR, True, 110)
        self.amm_2.set_prices(TRADING_PAIR, False, 109)
        self.amm_1.network_transaction_fee = TokenAmount("ETH", Decimal("0.01"))
        await asyncio.sleep(2)
        taker_orders = self.strategy.tracked_limit_orders + self.strategy.tracked_market_orders
        self.assertTrue(len(taker_orders) == 0)

    @async_test(loop=ev_loop)
    async def test_arb_profitable_after_gas_prices(self):
        self.amm_1.set_prices(TRADING_PAIR, True, 101)
        self.amm_1.set_prices(TRADING_PAIR, False, 100)
        self.amm_2.set_prices(TRADING_PAIR, True, 105)
        self.amm_2.set_prices(TRADING_PAIR, False, 104)
        self.amm_1.network_transaction_fee = TokenAmount("ETH", Decimal("0.0002"))
        await asyncio.sleep(2)
        placed_orders = self.strategy.tracked_limit_orders + self.strategy.tracked_market_orders
        self.assertEqual(2, len(placed_orders))

    @async_test(loop=ev_loop)
    @unittest.mock.patch("hummingbot.strategy.amm_arb.amm_arb.AmmArbStrategy.apply_gateway_transaction_cancel_interval")
    async def test_apply_cancel_interval(self, patched_func: unittest.mock.AsyncMock):
        await asyncio.sleep(2)
        patched_func.assert_awaited()

    @async_test(loop=ev_loop)
    @unittest.mock.patch("hummingbot.strategy.amm_arb.amm_arb.AmmArbStrategy.is_gateway_market", return_value=True)
    @unittest.mock.patch("hummingbot.client.settings.GatewayConnectionSetting.get_connector_spec_from_market_name")
    @unittest.mock.patch.object(MockAMM, "cancel_outdated_orders")
    async def test_cancel_outdated_orders(
            self,
            cancel_outdated_orders_func: unittest.mock.AsyncMock,
            get_connector_spec_from_market_name_mock: unittest.mock.MagicMock,
            _: unittest.mock.Mock
    ):
        get_connector_spec_from_market_name_mock.return_value = {
            "connector": "uniswap",
            "chain": "ethereum",
            "network": "mainnet",
            "trading_type": "AMM",
            "wallet_address": "0xA86b66F4e7DC45a943D71a11c7DDddE341246682",  # noqa: mock
        }
        await asyncio.sleep(2)
        cancel_outdated_orders_func.assert_awaited()

    @async_test(loop=ev_loop)
    async def test_set_order_failed(self):
        self.amm_1.set_prices(TRADING_PAIR, True, 101)
        self.amm_1.set_prices(TRADING_PAIR, False, 100)
        self.amm_2.set_prices(TRADING_PAIR, True, 105)
        self.amm_2.set_prices(TRADING_PAIR, False, 104)
        self.amm_1.network_transaction_fee = TokenAmount("ETH", Decimal("0.0002"))
        await asyncio.sleep(2)
        new_amm_1_order = [order for market, order in self.strategy.tracked_limit_orders if market == self.amm_1][0]
        self.assertEqual(2, len(self.strategy.tracked_limit_orders))
        self.strategy.set_order_failed(new_amm_1_order.client_order_id)
        self.assertEqual(2, len(self.strategy.tracked_limit_orders))

    @async_test(loop=ev_loop)
    async def test_market_ready(self):
        self.amm_1.ready = False
        await asyncio.sleep(10)
        self.assertFalse(self.strategy._all_markets_ready)
