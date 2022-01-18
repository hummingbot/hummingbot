import asyncio
import contextlib
from decimal import Decimal
import logging
import unittest
import unittest.mock

from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (MarketEvent, OrderType, BuyOrderCreatedEvent, BuyOrderCompletedEvent,
                                          SellOrderCreatedEvent, SellOrderCompletedEvent)
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.strategy.amm_arb.amm_arb import AmmArbStrategy
from hummingbot.strategy.amm_arb.data_types import ArbProposalSide, ArbProposal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

logging.basicConfig(level=METRICS_LOG_LEVEL)

trading_pair = "HBOT-USDT"
base_asset = trading_pair.split("-")[0]
quote_asset = trading_pair.split("-")[1]


class MockAMM(ConnectorBase):
    def __init__(self, name):
        self._name = name
        super().__init__()
        self._buy_prices = {}
        self._sell_prices = {}

    @property
    def name(self):
        return self._name

    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        if is_buy:
            return self._buy_prices[trading_pair]
        else:
            return self._sell_prices[trading_pair]

    def set_prices(self, trading_pair, is_buy, price):
        if is_buy:
            self._buy_prices[trading_pair] = Decimal(str(price))
        else:
            self._sell_prices[trading_pair] = Decimal(str(price))

    def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        return self.get_quote_price(trading_pair, is_buy, amount)

    def set_balance(self, token, balance):
        self._account_balances[token] = Decimal(str(balance))
        self._account_available_balances[token] = Decimal(str(balance))

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal):
        return self.place_order(True, trading_pair, amount, price)

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal):
        return self.place_order(False, trading_pair, amount, price)

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal):
        side = "buy" if is_buy else "sell"
        order_id = f"{side}-{trading_pair}-{get_tracking_nonce()}"
        event_tag = MarketEvent.BuyOrderCreated if is_buy else MarketEvent.SellOrderCreated
        event_class = BuyOrderCreatedEvent if is_buy else SellOrderCreatedEvent
        self.trigger_event(event_tag, event_class(self.current_timestamp, OrderType.LIMIT, trading_pair,
                                                  amount, price, order_id))
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


class AmmArbUnitTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.get_event_loop()
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.stack: contextlib.ExitStack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls._patcher = unittest.mock.patch("hummingbot.strategy.amm_arb.data_types.estimate_fee")
        cls._url_mock = cls._patcher.start()
        cls._url_mock.return_value = AddedToCostTradeFee(percent=0, flat_fees=[])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()
        cls._patcher.stop()

    def setUp(self):
        self.amm_1: MockAMM = MockAMM("onion")

        self.amm_1.set_balance(base_asset, 500)
        self.amm_1.set_balance(quote_asset, 500)
        self.market_info_1 = MarketTradingPairTuple(self.amm_1, trading_pair, base_asset, quote_asset)

        self.amm_2: MockAMM = MockAMM("garlic")
        self.amm_2.set_balance(base_asset, 500)
        self.amm_2.set_balance(quote_asset, 500)
        self.market_info_2 = MarketTradingPairTuple(self.amm_2, trading_pair, base_asset, quote_asset)
        self.strategy = AmmArbStrategy()
        self.strategy.init_params(
            self.market_info_1,
            self.market_info_2,
            min_profitability=Decimal("0.01"),
            order_amount=Decimal("1"),
            market_1_slippage_buffer=Decimal("0.001"),
            market_2_slippage_buffer=Decimal("0.002"),
        )
        self.clock.add_iterator(self.amm_1)
        self.clock.add_iterator(self.amm_2)
        self.clock.add_iterator(self.strategy)
        self.market_order_fill_logger: EventLogger = EventLogger()
        self.amm_1.add_listener(MarketEvent.OrderFilled, self.market_order_fill_logger)
        self.amm_2.add_listener(MarketEvent.OrderFilled, self.market_order_fill_logger)

    def test_arbitrage_not_profitable(self):
        self.amm_1.set_prices(trading_pair, True, 101)
        self.amm_1.set_prices(trading_pair, False, 100)
        self.amm_2.set_prices(trading_pair, True, 101)
        self.amm_2.set_prices(trading_pair, False, 100)
        self.ev_loop.run_until_complete(asyncio.sleep(2))
        taker_orders = self.strategy.tracked_limit_orders + self.strategy.tracked_market_orders
        self.assertTrue(len(taker_orders) == 0)

    def test_arb_buy_amm_1_sell_amm_2(self):
        asyncio.ensure_future(self.clock.run())
        self.amm_1.set_prices(trading_pair, True, 101)
        self.amm_1.set_prices(trading_pair, False, 100)
        self.amm_2.set_prices(trading_pair, True, 105)
        self.amm_2.set_prices(trading_pair, False, 104)
        self.ev_loop.run_until_complete(asyncio.sleep(1.5))
        placed_orders = self.strategy.tracked_limit_orders
        amm_1_order = [order for market, order in placed_orders if market == self.amm_1][0]
        amm_2_order = [order for market, order in placed_orders if market == self.amm_2][0]

        self.assertTrue(len(placed_orders) == 2)
        # Check if the order is created as intended
        self.assertEqual(Decimal("1"), amm_1_order.quantity)
        self.assertEqual(True, amm_1_order.is_buy)
        # The order price has to account for slippage_buffer
        exp_price = self.amm_1.quantize_order_price(trading_pair, Decimal("101") * Decimal("1.001"))
        self.assertEqual(exp_price, amm_1_order.price)
        self.assertEqual(trading_pair, amm_1_order.trading_pair)

        self.assertEqual(Decimal("1"), amm_2_order.quantity)
        self.assertEqual(False, amm_2_order.is_buy)
        exp_price = self.amm_1.quantize_order_price(trading_pair, Decimal("104") * (Decimal("1") - Decimal("0.002")))
        self.assertEqual(exp_price, amm_2_order.price)
        self.assertEqual(trading_pair, amm_2_order.trading_pair)

        # There are outstanding orders, the strategy is not ready to take on new arb
        self.assertFalse(self.strategy.ready_for_new_arb_trades())
        self.ev_loop.run_until_complete(asyncio.sleep(2))
        placed_orders = self.strategy.tracked_limit_orders
        new_amm_1_order = [order for market, order in placed_orders if market == self.amm_1][0]
        new_amm_2_order = [order for market, order in placed_orders if market == self.amm_2][0]
        # Check if orders remain the same
        self.assertEqual(amm_1_order.client_order_id, new_amm_1_order.client_order_id)
        self.assertEqual(amm_2_order.client_order_id, new_amm_2_order.client_order_id)

    def test_arb_buy_amm_2_sell_amm_1(self):
        asyncio.ensure_future(self.clock.run())
        self.amm_1.set_prices(trading_pair, True, 105)
        self.amm_1.set_prices(trading_pair, False, 104)
        self.amm_2.set_prices(trading_pair, True, 101)
        self.amm_2.set_prices(trading_pair, False, 100)
        self.ev_loop.run_until_complete(asyncio.sleep(1.5))
        placed_orders = self.strategy.tracked_limit_orders
        amm_1_order = [order for market, order in placed_orders if market == self.amm_1][0]
        amm_2_order = [order for market, order in placed_orders if market == self.amm_2][0]

        self.assertTrue(len(placed_orders) == 2)
        self.assertEqual(Decimal("1"), amm_1_order.quantity)
        self.assertEqual(False, amm_1_order.is_buy)
        exp_price = self.amm_1.quantize_order_price(trading_pair, Decimal("104") * (Decimal("1") - Decimal("0.001")))
        self.assertEqual(exp_price, amm_1_order.price)
        self.assertEqual(trading_pair, amm_1_order.trading_pair)
        self.assertEqual(Decimal("1"), amm_2_order.quantity)
        self.assertEqual(True, amm_2_order.is_buy)
        exp_price = self.amm_1.quantize_order_price(trading_pair, Decimal("101") * (Decimal("1") + Decimal("0.002")))
        self.assertEqual(exp_price, amm_2_order.price)
        self.assertEqual(trading_pair, amm_2_order.trading_pair)

    def test_insufficient_balance(self):
        self.amm_1.set_prices(trading_pair, True, 105)
        self.amm_1.set_prices(trading_pair, False, 104)
        self.amm_2.set_prices(trading_pair, True, 101)
        self.amm_2.set_prices(trading_pair, False, 100)
        # set base_asset to below order_amount, so not enough to sell on amm_1
        self.amm_1.set_balance(base_asset, 0.5)
        asyncio.ensure_future(self.clock.run())
        self.ev_loop.run_until_complete(asyncio.sleep(1.5))
        placed_orders = self.strategy.tracked_limit_orders
        self.assertTrue(len(placed_orders) == 0)
        self.amm_1.set_balance(base_asset, 10)
        # set quote balance to 0 on amm_2, so not enough to buy
        self.amm_2.set_balance(quote_asset, 0)
        asyncio.ensure_future(self.clock.run())
        self.ev_loop.run_until_complete(asyncio.sleep(1.5))
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
                                event_class(connector.current_timestamp, order_id, base_asset, quote_asset,
                                            quote_asset, amount, amount * price, Decimal("0"), OrderType.LIMIT))

    def test_non_concurrent_orders_submission(self):
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
        self.clock.add_iterator(self.strategy)
        asyncio.ensure_future(self.clock.run())
        self.amm_1.set_prices(trading_pair, True, 101)
        self.amm_1.set_prices(trading_pair, False, 100)
        self.amm_2.set_prices(trading_pair, True, 105)
        self.amm_2.set_prices(trading_pair, False, 104)
        self.ev_loop.run_until_complete(asyncio.sleep(1.5))
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
        self.ev_loop.run_until_complete(asyncio.sleep(1.5))
        placed_orders = self.strategy.tracked_limit_orders
        amm_2_orders = [order for market, order in placed_orders if market == self.amm_2]
        self.assertEqual(1, len(amm_2_orders))
        amm_2_order = amm_2_orders[0]
        self.assertEqual(False, amm_2_order.is_buy)
        self.trigger_order_complete(False, self.amm_2, amm_2_order.quantity, amm_2_order.price,
                                    amm_2_order.client_order_id)
        self.ev_loop.run_until_complete(asyncio.sleep(1.5))
        placed_orders = self.strategy.tracked_limit_orders
        new_amm_1_order = [order for market, order in placed_orders if market == self.amm_1][0]
        # Check if new order is submitted when arb opportunity still presents
        self.assertNotEqual(amm_1_order.client_order_id, new_amm_1_order.client_order_id)

    def test_format_status(self):
        self.amm_1.set_prices(trading_pair, True, 101)
        self.amm_1.set_prices(trading_pair, False, 100)
        self.amm_2.set_prices(trading_pair, True, 105)
        self.amm_2.set_prices(trading_pair, False, 104)

        first_side = ArbProposalSide(
            self.market_info_1,
            True,
            Decimal(101),
            Decimal(100),
            Decimal(50)
        )
        second_side = ArbProposalSide(
            self.market_info_2,
            False,
            Decimal(105),
            Decimal(104),
            Decimal(50)
        )
        self.strategy._arb_proposals = [ArbProposal(first_side, second_side)]

        expected_status = ("  Markets:\n"
                           "    Exchange    Market   Sell Price    Buy Price    Mid Price\n"
                           "       onion HBOT-USDT 100.00000000 101.00000000 100.50000000\n"
                           "      garlic HBOT-USDT 104.00000000 105.00000000 104.50000000\n\n"
                           "  Assets:\n"
                           "      Exchange Asset  Total Balance  Available Balance\n"
                           "    0    onion  HBOT            500                500\n"
                           "    1    onion  USDT            500                500\n"
                           "    2   garlic  HBOT            500                500\n"
                           "    3   garlic  USDT            500                500\n\n"
                           "  Profitability:\n"
                           "    buy at onion, sell at garlic: 3.96%\n\n"
                           "  Quotes Rates (fixed rates)\n"
                           "      Quotes pair Rate\n"
                           "    0   USDT-USDT    1")

        current_status = self.ev_loop.run_until_complete(self.strategy.format_status())
        self.assertTrue(expected_status in current_status)
