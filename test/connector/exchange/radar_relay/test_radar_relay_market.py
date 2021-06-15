#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import asyncio
import conf
import contextlib
from decimal import Decimal
import logging
import os
import time
from typing import (
    List,
    Optional
)
import unittest

from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    MarketEvent,
    WalletEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    WalletWrappedEthEvent,
    WalletUnwrappedEthEvent,
    OrderCancelledEvent,
    OrderExpiredEvent,
    OrderFilledEvent,
    TradeType,
    TradeFee,
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.logger import NETWORK
from hummingbot.core.event.events import OrderType
from hummingbot.connector.markets_recorder import MarketsRecorder
from hummingbot.connector.exchange.radar_relay.radar_relay_exchange import RadarRelayExchange
from hummingbot.model.market_state import MarketState
from hummingbot.model.order import Order
from hummingbot.model.sql_connection_manager import (
    SQLConnectionManager,
    SQLConnectionType
)
from hummingbot.model.trade_fill import TradeFill
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.wallet.ethereum.web3_wallet_backend import EthereumChain

s_decimal_0 = Decimal(0)


class RadarRelayExchangeUnitTest(unittest.TestCase):
    market_events: List[MarketEvent] = [
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderExpired,
        MarketEvent.OrderFilled,
    ]

    wallet_events: List[WalletEvent] = [
        WalletEvent.WrappedEth,
        WalletEvent.UnwrappedEth
    ]

    wallet: Web3Wallet
    market: RadarRelayExchange
    market_logger: EventLogger
    wallet_logger: EventLogger
    stack: contextlib.ExitStack

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.wallet = Web3Wallet(private_key=conf.web3_private_key_radar,
                                backend_urls=conf.test_web3_provider_list,
                                erc20_token_addresses=[conf.mn_zerox_token_address, conf.mn_weth_token_address],
                                chain=EthereumChain.MAIN_NET)
        cls.market = RadarRelayExchange(
            wallet=cls.wallet,
            ethereum_rpc_url=conf.test_web3_provider_list[0],
            trading_pairs=["ZRX-WETH"]
        )
        print("Initializing Radar Relay market... ")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.wallet)
        cls.clock.add_iterator(cls.market)
        cls.stack = contextlib.ExitStack()
        cls._clock = cls.stack.enter_context(cls.clock)
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stack.close()

    @classmethod
    async def wait_til_ready(cls):
        while True:
            now = time.time()
            next_iteration = now // 1.0 + 1
            if cls.market.ready:
                break
            else:
                await cls._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)

    def setUp(self):
        self.db_path: str = realpath(join(__file__, "../radar_relay_test.sqlite"))
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

        self.market_logger = EventLogger()
        self.wallet_logger = EventLogger()
        for event_tag in self.market_events:
            self.market.add_listener(event_tag, self.market_logger)
        for event_tag in self.wallet_events:
            self.wallet.add_listener(event_tag, self.wallet_logger)

    def tearDown(self):
        for event_tag in self.market_events:
            self.market.remove_listener(event_tag, self.market_logger)
        self.market_logger = None
        for event_tag in self.wallet_events:
            self.wallet.remove_listener(event_tag, self.wallet_logger)
        self.wallet_logger = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self._clock.run_til(next_iteration)
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        maker_buy_trade_fee: TradeFee = self.market.get_fee("ZRX", "WETH", OrderType.LIMIT, TradeType.BUY, Decimal(20), Decimal(0.01))
        self.assertEqual(maker_buy_trade_fee.percent, 0)
        self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
        taker_buy_trade_fee: TradeFee = self.market.get_fee("ZRX", "WETH", OrderType.MARKET, TradeType.BUY, Decimal(20))
        self.assertEqual(taker_buy_trade_fee.percent, 0)
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 1)
        self.assertEqual(taker_buy_trade_fee.flat_fees[0][0], "ETH")

    def test_get_wallet_balances(self):
        balances = self.market.get_all_balances()
        self.assertGreaterEqual((balances["ETH"]), s_decimal_0)
        self.assertGreaterEqual((balances["WETH"]), s_decimal_0)

    def test_single_limit_order_cancel(self):
        trading_pair: str = "ZRX-WETH"
        current_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal(10)
        expires = int(time.time() + 60 * 5)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)
        buy_order_id = self.market.buy(trading_pair=trading_pair,
                                       amount=amount,
                                       order_type=OrderType.LIMIT,
                                       price=current_price * Decimal("0.8"),
                                       expiration_ts=expires)
        [buy_order_opened_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual("ZRX-WETH", buy_order_opened_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, buy_order_opened_event.type)
        self.assertEqual(quantized_amount, Decimal(buy_order_opened_event.amount))

        self.run_parallel(self.market.cancel_order(buy_order_id))
        [buy_order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(buy_order_opened_event.order_id, buy_order_cancelled_event.order_id)

        # Reset the logs
        self.market_logger.clear()

    def test_limit_buy_and_sell_and_cancel_all(self):
        trading_pair: str = "ZRX-WETH"
        current_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal(10)
        expires = int(time.time() + 60 * 5)
        quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, amount)
        buy_order_id = self.market.buy(trading_pair=trading_pair,
                                       amount=amount,
                                       order_type=OrderType.LIMIT,
                                       price=current_price * Decimal("0.8"),
                                       expiration_ts=expires)
        [buy_order_opened_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(buy_order_id, buy_order_opened_event.order_id)
        self.assertEqual(quantized_amount, Decimal(buy_order_opened_event.amount))
        self.assertEqual("ZRX-WETH", buy_order_opened_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, buy_order_opened_event.type)

        # Reset the logs
        self.market_logger.clear()

        sell_order_id = self.market.sell(trading_pair=trading_pair,
                                         amount=amount,
                                         order_type=OrderType.LIMIT,
                                         price=current_price * Decimal("1.2"),
                                         expiration_ts=expires)
        [sell_order_opened_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        self.assertEqual(sell_order_id, sell_order_opened_event.order_id)
        self.assertEqual(quantized_amount, Decimal(sell_order_opened_event.amount))
        self.assertEqual("ZRX-WETH", sell_order_opened_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, sell_order_opened_event.type)

        [cancellation_results] = self.run_parallel(self.market.cancel_all(60 * 5))
        self.assertEqual(cancellation_results[0], CancellationResult(buy_order_id, True))
        self.assertEqual(cancellation_results[1], CancellationResult(sell_order_id, True))
        # Reset the logs
        self.market_logger.clear()

    def test_order_expire(self):
        trading_pair: str = "ZRX-WETH"
        current_price: Decimal = self.market.get_price(trading_pair, True)
        amount: Decimal = Decimal(10)
        expires = int(time.time() + 60 * 2)  # expires in 2 min
        self.market.buy(trading_pair=trading_pair,
                        amount=amount,
                        order_type=OrderType.LIMIT,
                        price=current_price * Decimal("0.8"),
                        expiration_ts=expires)
        [buy_order_opened_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))

        self.assertEqual("ZRX-WETH", buy_order_opened_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, buy_order_opened_event.type)
        [buy_order_expired_event] = self.run_parallel(self.market_logger.wait_for(OrderExpiredEvent, 60 * 3))
        self.assertEqual(buy_order_opened_event.order_id, buy_order_expired_event.order_id)

        # Reset the logs
        self.market_logger.clear()

    def test_market_buy(self):
        amount: Decimal = Decimal(5)
        quantized_amount: Decimal = self.market.quantize_order_amount("ZRX-WETH", amount)
        order_id = self.market.buy("ZRX-WETH", amount, OrderType.MARKET)

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))
        order_completed_event: BuyOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(float(quantized_amount), float(order_completed_event.base_asset_amount))
        self.assertEqual("ZRX", order_completed_event.base_asset)
        self.assertEqual("WETH", order_completed_event.quote_asset)
        self.market_logger.clear()

    def test_market_sell(self):
        amount: Decimal = Decimal(5)
        quantized_amount: Decimal = self.market.quantize_order_amount("ZRX-WETH", amount)
        order_id = self.market.sell("ZRX-WETH", amount, OrderType.MARKET)

        [order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))
        order_completed_event: SellOrderCompletedEvent = order_completed_event
        order_filled_events: List[OrderFilledEvent] = [t for t in self.market_logger.event_log
                                                       if isinstance(t, OrderFilledEvent)]

        self.assertTrue([evt.order_type == OrderType.MARKET for evt in order_filled_events])
        self.assertEqual(order_id, order_completed_event.order_id)
        self.assertEqual(float(quantized_amount), float(order_completed_event.base_asset_amount))
        self.assertEqual("ZRX", order_completed_event.base_asset)
        self.assertEqual("WETH", order_completed_event.quote_asset)
        self.market_logger.clear()

    def test_wrap_eth(self):
        amount_to_wrap = Decimal("0.01")
        tx_hash = self.wallet.wrap_eth(amount_to_wrap)
        [tx_completed_event] = self.run_parallel(self.wallet_logger.wait_for(WalletWrappedEthEvent))
        tx_completed_event: WalletWrappedEthEvent = tx_completed_event

        self.assertEqual(tx_hash, tx_completed_event.tx_hash)
        self.assertEqual(amount_to_wrap, tx_completed_event.amount)
        self.assertEqual(self.wallet.address, tx_completed_event.address)

    def test_unwrap_eth(self):
        amount_to_unwrap = Decimal("0.01")
        tx_hash = self.wallet.unwrap_eth(amount_to_unwrap)
        [tx_completed_event] = self.run_parallel(self.wallet_logger.wait_for(WalletUnwrappedEthEvent))
        tx_completed_event: WalletUnwrappedEthEvent = tx_completed_event

        self.assertEqual(tx_hash, tx_completed_event.tx_hash)
        self.assertEqual(amount_to_unwrap, tx_completed_event.amount)
        self.assertEqual(self.wallet.address, tx_completed_event.address)

    def test_orders_saving_and_restoration(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ZRX-WETH"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            self.assertEqual(0, len(self.market.tracking_states["limit_orders"]))

            # Try to put limit buy order for 0.05 ETH worth of ZRX, and watch for order creation event.
            current_bid_price: Decimal = self.market.get_price(trading_pair, True)
            bid_price: Decimal = current_bid_price * Decimal(0.8)
            quantize_bid_price: Decimal = self.market.quantize_order_price(trading_pair, bid_price)

            amount: float = Decimal("0.05") / bid_price
            quantized_amount: Decimal = self.market.quantize_order_amount(trading_pair, Decimal(amount))

            expires = int(time.time() + 60 * 5)
            order_id = self.market.buy(trading_pair, quantized_amount, OrderType.LIMIT, quantize_bid_price,
                                       expiration_ts=expires)
            [order_created_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
            order_created_event: BuyOrderCreatedEvent = order_created_event
            self.assertEqual(order_id, order_created_event.order_id)

            # Verify tracking states
            self.assertEqual(1, len(self.market.tracking_states["limit_orders"]))
            self.assertEqual(order_id, list(self.market.tracking_states["limit_orders"].keys())[0])

            # Verify orders from recorder
            recorded_orders: List[Order] = recorder.get_orders_for_config_and_market(config_path, self.market)
            self.assertEqual(1, len(recorded_orders))
            self.assertEqual(order_id, recorded_orders[0].id)

            # Verify saved market states
            saved_market_states: MarketState = recorder.get_market_states(config_path, self.market)
            self.assertIsNotNone(saved_market_states)
            self.assertIsInstance(saved_market_states.saved_state, dict)
            self.assertIsInstance(saved_market_states.saved_state["limit_orders"], dict)
            self.assertGreater(len(saved_market_states.saved_state["limit_orders"]), 0)

            # Close out the current market and start another market.
            self.clock.remove_iterator(self.market)
            for event_tag in self.market_events:
                self.market.remove_listener(event_tag, self.market_logger)
            self.market = RadarRelayExchange(
                wallet=self.wallet,
                ethereum_rpc_url=conf.test_web3_provider_list[0],
                trading_pairs=["ZRX-WETH"]
            )
            for event_tag in self.market_events:
                self.market.add_listener(event_tag, self.market_logger)
            recorder.stop()
            recorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
            recorder.start()
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.clock.add_iterator(self.market)
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(0, len(self.market.tracking_states["limit_orders"]))
            self.market.restore_tracking_states(saved_market_states.saved_state)
            self.assertEqual(1, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states["limit_orders"]))

            # Cancel the order and verify that the change is saved.
            self.market.cancel(trading_pair, order_id)
            self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
            order_id = None
            self.assertEqual(0, len(self.market.limit_orders))
            self.assertEqual(1, len(self.market.tracking_states["limit_orders"]))
            saved_market_states = recorder.get_market_states(config_path, self.market)
            self.assertEqual(1, len(saved_market_states.saved_state["limit_orders"]))
        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)

    def test_order_fill_record(self):
        config_path: str = "test_config"
        strategy_name: str = "test_strategy"
        trading_pair: str = "ZRX-WETH"
        sql: SQLConnectionManager = SQLConnectionManager(SQLConnectionType.TRADE_FILLS, db_path=self.db_path)
        order_id: Optional[str] = None
        recorder: MarketsRecorder = MarketsRecorder(sql, [self.market], config_path, strategy_name)
        recorder.start()

        try:
            # Try to buy 0.05 ETH worth of ZRX from the exchange, and watch for completion event.
            current_price: Decimal = self.market.get_price(trading_pair, True)
            amount: Decimal = Decimal("0.05") / current_price
            order_id = self.market.buy(trading_pair, amount)
            [buy_order_completed_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCompletedEvent))

            # Reset the logs
            self.market_logger.clear()

            # Try to sell back the same amount of ZRX to the exchange, and watch for completion event.
            amount = Decimal(buy_order_completed_event.base_asset_amount)
            order_id = self.market.sell(trading_pair, amount)
            [sell_order_completed_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCompletedEvent))

            # Query the persisted trade logs
            trade_fills: List[TradeFill] = recorder.get_trades_for_config(config_path)
            self.assertEqual(2, len(trade_fills))
            buy_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "BUY"]
            sell_fills: List[TradeFill] = [t for t in trade_fills if t.trade_type == "SELL"]
            self.assertEqual(1, len(buy_fills))
            self.assertEqual(1, len(sell_fills))

            order_id = None

        finally:
            if order_id is not None:
                self.market.cancel(trading_pair, order_id)
                self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))

            recorder.stop()
            os.unlink(self.db_path)


def main():
    logging.basicConfig(level=NETWORK)
    unittest.main()


if __name__ == "__main__":
    main()
