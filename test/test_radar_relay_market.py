#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import conf
import time
import asyncio
from decimal import Decimal
import logging
import unittest
from typing import List
from wings.cancellation_result import CancellationResult
from wings.market.market_base import OrderType
from wings.wallet.web3_wallet import Web3Wallet
from wings.wallet.web3_wallet_backend import EthereumChain
from wings.clock import Clock, ClockMode
from wings.market.radar_relay_market import RadarRelayMarket
from wings.event_logger import EventLogger
from wings.order_book_tracker import OrderBookTrackerDataSourceType
from wings.events import (
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
    TradeFee
)


class RadarRelayMarketUnitTest(unittest.TestCase):
    market_events: List[MarketEvent] = [
        MarketEvent.ReceivedAsset,
        MarketEvent.BuyOrderCompleted,
        MarketEvent.SellOrderCompleted,
        MarketEvent.BuyOrderCreated,
        MarketEvent.SellOrderCreated,
        MarketEvent.OrderCancelled,
        MarketEvent.OrderExpired,
        MarketEvent.OrderFilled,
        MarketEvent.WithdrawAsset
    ]

    wallet_events: List[WalletEvent] = [
        WalletEvent.WrappedEth,
        WalletEvent.UnwrappedEth
    ]

    wallet: Web3Wallet
    market: RadarRelayMarket
    market_logger: EventLogger
    wallet_logger: EventLogger

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.wallet = Web3Wallet(private_key=conf.web3_private_key_radar,
                                backend_urls=conf.test_web3_provider_list,
                                erc20_token_addresses=[conf.mn_zerox_token_address, conf.mn_weth_token_address],
                                chain=EthereumChain.MAIN_NET)
        cls.market: RadarRelayMarket = RadarRelayMarket(wallet=cls.wallet,
                                                        web3_url=conf.test_web3_provider_list[0],
                                                        order_book_tracker_data_source_type=
                                                            OrderBookTrackerDataSourceType.EXCHANGE_API,
                                                        symbols=["ZRX-WETH"])
        print("Initializing Radar Relay market... ")
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.clock.add_iterator(cls.wallet)
        cls.clock.add_iterator(cls.market)
        cls.ev_loop.run_until_complete(cls.clock.run_til(time.time() + 1))
        cls.ev_loop.run_until_complete(cls.wait_til_ready())
        print("Ready.")

    @classmethod
    async def wait_til_ready(cls):
        while True:
            if cls.market.ready:
                break
            await asyncio.sleep(1.0)

    def setUp(self):
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
        future: asyncio.Future = asyncio.ensure_future(asyncio.gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_get_fee(self):
        maker_buy_trade_fee: TradeFee = self.market.get_fee("ZRX-WETH", OrderType.LIMIT, TradeType.BUY, 20, 0.01)
        self.assertEqual(maker_buy_trade_fee.percent, 0)
        self.assertEqual(len(maker_buy_trade_fee.flat_fees), 0)
        taker_buy_trade_fee: TradeFee = self.market.get_fee("ZRX-WETH", OrderType.MARKET, TradeType.BUY, 20)
        self.assertEqual(taker_buy_trade_fee.percent, 0)
        self.assertEqual(len(taker_buy_trade_fee.flat_fees), 1)
        self.assertEqual(taker_buy_trade_fee.flat_fees[0][0], "ETH")

    def test_get_wallet_balances(self):
        balances = self.market.get_all_balances()
        self.assertGreaterEqual((balances["ETH"]), 0)
        self.assertGreaterEqual((balances["WETH"]), 0)

    def test_single_limit_order_cancel(self):
        symbol: str = "ZRX-WETH"
        current_price: float = self.market.get_price(symbol, True)
        amount: float = 10
        expires = int(time.time() + 60 * 5)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)
        buy_order_id = self.market.buy(symbol=symbol,
                                       amount=amount,
                                       order_type=OrderType.LIMIT,
                                       price=current_price - 0.2 * current_price,
                                       expiration_ts=expires)
        [buy_order_opened_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual("ZRX-WETH", buy_order_opened_event.symbol)
        self.assertEqual(OrderType.LIMIT, buy_order_opened_event.type)
        self.assertEqual(quantized_amount, Decimal(buy_order_opened_event.amount))

        self.run_parallel(self.market.cancel_order(buy_order_id))
        [buy_order_cancelled_event] = self.run_parallel(self.market_logger.wait_for(OrderCancelledEvent))
        self.assertEqual(buy_order_opened_event.order_id, buy_order_cancelled_event.order_id)

        # Reset the logs
        self.market_logger.clear()

    def test_limit_buy_and_sell_and_cancel_all(self):
        symbol: str = "ZRX-WETH"
        current_price: float = self.market.get_price(symbol, True)
        amount: float = 10
        expires = int(time.time() + 60 * 5)
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)
        buy_order_id = self.market.buy(symbol=symbol,
                                       amount=amount,
                                       order_type=OrderType.LIMIT,
                                       price=current_price - 0.2 * current_price,
                                       expiration_ts=expires)
        [buy_order_opened_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))
        self.assertEqual(buy_order_id, buy_order_opened_event.order_id)
        self.assertEqual(quantized_amount, Decimal(buy_order_opened_event.amount))
        self.assertEqual("ZRX-WETH", buy_order_opened_event.symbol)
        self.assertEqual(OrderType.LIMIT, buy_order_opened_event.type)

        # Reset the logs
        self.market_logger.clear()

        sell_order_id = self.market.sell(symbol=symbol,
                                         amount=amount,
                                         order_type=OrderType.LIMIT,
                                         price=current_price + 0.2 * current_price,
                                         expiration_ts=expires)
        [sell_order_opened_event] = self.run_parallel(self.market_logger.wait_for(SellOrderCreatedEvent))
        self.assertEqual(sell_order_id, sell_order_opened_event.order_id)
        self.assertEqual(quantized_amount, Decimal(sell_order_opened_event.amount))
        self.assertEqual("ZRX-WETH", sell_order_opened_event.symbol)
        self.assertEqual(OrderType.LIMIT, sell_order_opened_event.type)

        [cancellation_results] = self.run_parallel(self.market.cancel_all(60 * 5))
        self.assertEqual(cancellation_results[0], CancellationResult(buy_order_id, True))
        self.assertEqual(cancellation_results[1], CancellationResult(sell_order_id, True))
        # Reset the logs
        self.market_logger.clear()

    def test_order_expire(self):
        symbol: str = "ZRX-WETH"
        current_price: float = self.market.get_price(symbol, True)
        amount: float = 10
        expires = int(time.time() + 60 * 2) # expires in 2 min
        quantized_amount: Decimal = self.market.quantize_order_amount(symbol, amount)
        buy_order_id = self.market.buy(symbol=symbol,
                                       amount=amount,
                                       order_type=OrderType.LIMIT,
                                       price=current_price - 0.2 * current_price,
                                       expiration_ts=expires)
        [buy_order_opened_event] = self.run_parallel(self.market_logger.wait_for(BuyOrderCreatedEvent))

        self.assertEqual("ZRX-WETH", buy_order_opened_event.symbol)
        self.assertEqual(OrderType.LIMIT, buy_order_opened_event.type)
        [buy_order_expired_event] = self.run_parallel(self.market_logger.wait_for(OrderExpiredEvent, 60 * 3))
        self.assertEqual(buy_order_opened_event.order_id, buy_order_expired_event.order_id)

        # Reset the logs
        self.market_logger.clear()

    def test_market_buy(self):
        amount: float = 5
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
        amount: float = 5
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
        amount_to_wrap = 0.01
        tx_hash = self.wallet.wrap_eth(amount_to_wrap)
        [tx_completed_event] = self.run_parallel(self.wallet_logger.wait_for(WalletWrappedEthEvent))
        tx_completed_event: WalletWrappedEthEvent = tx_completed_event

        self.assertEqual(tx_hash, tx_completed_event.tx_hash)
        self.assertEqual(amount_to_wrap, tx_completed_event.amount)
        self.assertEqual(self.wallet.address, tx_completed_event.address)

    def test_unwrap_eth(self):
        amount_to_unwrap = 0.01
        tx_hash = self.wallet.unwrap_eth(amount_to_unwrap)
        [tx_completed_event] = self.run_parallel(self.wallet_logger.wait_for(WalletUnwrappedEthEvent))
        tx_completed_event: WalletUnwrappedEthEvent = tx_completed_event

        self.assertEqual(tx_hash, tx_completed_event.tx_hash)
        self.assertEqual(amount_to_unwrap, tx_completed_event.amount)
        self.assertEqual(self.wallet.address, tx_completed_event.address)


def main():
    logging.basicConfig(level=logging.ERROR)
    unittest.main()


if __name__ == "__main__":
    main()
