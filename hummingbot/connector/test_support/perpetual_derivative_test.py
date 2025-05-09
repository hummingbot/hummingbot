import asyncio
import json
from abc import abstractmethod
from decimal import Decimal
from typing import Callable, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.derivative.position import Position
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PositionSide, TradeType
from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    BuyOrderCompletedEvent,
    BuyOrderCreatedEvent,
    FundingPaymentCompletedEvent,
    MarketEvent,
    OrderFilledEvent,
    SellOrderCompletedEvent,
    SellOrderCreatedEvent,
)


class AbstractPerpetualDerivativeTests:
    """
    We need to create the abstract TestCase class inside another class not inheriting from TestCase to prevent test
    frameworks from discovering and tyring to run the abstract class
    """

    class PerpetualDerivativeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):
        @property
        @abstractmethod
        def expected_supported_position_modes(self) -> List[PositionMode]:
            raise NotImplementedError

        @property
        @abstractmethod
        def funding_info_url(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def funding_payment_url(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def funding_info_mock_response(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def empty_funding_payment_mock_response(self):
            raise NotImplementedError

        @property
        @abstractmethod
        def funding_payment_mock_response(self):
            raise NotImplementedError

        @property
        def target_funding_info_index_price(self):
            return 1

        @property
        def target_funding_info_mark_price(self):
            return 2

        @property
        def target_funding_info_next_funding_utc_timestamp(self):
            return 1657099053

        @property
        def target_funding_info_rate(self):
            return 3

        @property
        def target_funding_info_index_price_ws_updated(self):
            return 10

        @property
        def target_funding_info_mark_price_ws_updated(self):
            return 20

        @property
        def target_funding_info_next_funding_utc_timestamp_ws_updated(self):
            return 1657100053

        @property
        def target_funding_info_rate_ws_updated(self):
            return 30

        @property
        def target_funding_payment_timestamp(self):
            return 1657110053

        @property
        def target_funding_payment_funding_rate(self):
            return 100

        @property
        def target_funding_payment_payment_amount(self):
            return 200

        @abstractmethod
        def position_event_for_full_fill_websocket_update(self, order: InFlightOrder, unrealized_pnl: float):
            raise NotImplementedError

        @abstractmethod
        def configure_successful_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ):
            raise NotImplementedError

        @abstractmethod
        def configure_failed_set_position_mode(
            self,
            position_mode: PositionMode,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> Tuple[str, str]:
            """
            :return: A tuple of the URL and an error message if the exchange returns one on failure.
            """
            raise NotImplementedError

        @abstractmethod
        def configure_failed_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ) -> Tuple[str, str]:
            """
            :return: A tuple of the URL and an error message if the exchange returns one on failure.
            """
            raise NotImplementedError

        @abstractmethod
        def configure_successful_set_leverage(
            self,
            leverage: int,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None,
        ):
            raise NotImplementedError

        @abstractmethod
        def funding_info_event_for_websocket_update(self):
            raise NotImplementedError

        def place_buy_order(
            self,
            amount: Decimal = Decimal("100"),
            price: Decimal = Decimal("10_000"),
            order_type: OrderType = OrderType.LIMIT,
            position_action: PositionAction = PositionAction.OPEN,
        ):
            order_id = self.exchange.buy(
                trading_pair=self.trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                position_action=position_action,
            )
            return order_id

        def place_sell_order(
            self,
            amount: Decimal = Decimal("100"),
            price: Decimal = Decimal("10_000"),
            order_type: OrderType = OrderType.LIMIT,
            position_action: PositionAction = PositionAction.OPEN,
        ):
            order_id = self.exchange.sell(
                trading_pair=self.trading_pair,
                amount=amount,
                order_type=order_type,
                price=price,
                position_action=position_action,
            )
            return order_id

        def _initialize_event_loggers(self):
            super()._initialize_event_loggers()
            self.funding_payment_logger = EventLogger()
            self.exchange.add_listener(MarketEvent.FundingPaymentCompleted, self.funding_payment_logger)

        def test_initial_status_dict(self):
            self.exchange._set_trading_pair_symbol_map(None)
            self.exchange._perpetual_trading._funding_info = {}

            status_dict = self.exchange.status_dict

            expected_initial_dict = self._expected_initial_status_dict()
            expected_initial_dict["funding_info"] = False

            self.assertEqual(expected_initial_dict, status_dict)
            self.assertFalse(self.exchange.ready)

        @aioresponses()
        def test_create_buy_limit_order_successfully(self, mock_api):
            """Open long position"""
            self._simulate_trading_rules_initialized()
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)

            url = self.order_creation_url

            creation_response = self.order_creation_request_successful_mock_response

            mock_api.post(url,
                          body=json.dumps(creation_response),
                          callback=lambda *args, **kwargs: request_sent_event.set())

            leverage = 2
            self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
            order_id = self.place_buy_order()
            self.async_run_with_timeout(request_sent_event.wait())

            order_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_request)
            self.assertIn(order_id, self.exchange.in_flight_orders)
            self.validate_order_creation_request(
                order=self.exchange.in_flight_orders[order_id],
                request_call=order_request)

            create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp,
                             create_event.timestamp)
            self.assertEqual(self.trading_pair, create_event.trading_pair)
            self.assertEqual(OrderType.LIMIT, create_event.type)
            self.assertEqual(Decimal("100"), create_event.amount)
            self.assertEqual(Decimal("10000"), create_event.price)
            self.assertEqual(order_id, create_event.order_id)
            self.assertEqual(str(self.expected_exchange_order_id),
                             create_event.exchange_order_id)
            self.assertEqual(leverage, create_event.leverage)
            self.assertEqual(PositionAction.OPEN.value, create_event.position)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                    f"{Decimal('100.000000')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
                    f"at {Decimal('10000.0000')}."
                )
            )

        @aioresponses()
        def test_create_sell_limit_order_successfully(self, mock_api):
            """Open short position"""
            self._simulate_trading_rules_initialized()
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)

            url = self.order_creation_url
            creation_response = self.order_creation_request_successful_mock_response

            mock_api.post(url,
                          body=json.dumps(creation_response),
                          callback=lambda *args, **kwargs: request_sent_event.set())
            leverage = 3
            self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
            order_id = self.place_sell_order()
            self.async_run_with_timeout(request_sent_event.wait())

            order_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_request)
            self.assertIn(order_id, self.exchange.in_flight_orders)
            self.validate_order_creation_request(
                order=self.exchange.in_flight_orders[order_id],
                request_call=order_request)

            create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
            self.assertEqual(self.trading_pair, create_event.trading_pair)
            self.assertEqual(OrderType.LIMIT, create_event.type)
            self.assertEqual(Decimal("100"), create_event.amount)
            self.assertEqual(Decimal("10000"), create_event.price)
            self.assertEqual(order_id, create_event.order_id)
            self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)
            self.assertEqual(leverage, create_event.leverage)
            self.assertEqual(PositionAction.OPEN.value, create_event.position)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                    f"{Decimal('100.000000')} to {PositionAction.OPEN.name} a {self.trading_pair} position "
                    f"at {Decimal('10000.0000')}."
                )
            )

        @aioresponses()
        def test_create_order_to_close_short_position(self, mock_api):
            self._simulate_trading_rules_initialized()
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)

            url = self.order_creation_url

            creation_response = self.order_creation_request_successful_mock_response

            mock_api.post(url,
                          body=json.dumps(creation_response),
                          callback=lambda *args, **kwargs: request_sent_event.set())
            leverage = 4
            self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
            order_id = self.place_buy_order(position_action=PositionAction.CLOSE)
            self.async_run_with_timeout(request_sent_event.wait())

            order_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_request)
            self.assertIn(order_id, self.exchange.in_flight_orders)
            self.validate_order_creation_request(
                order=self.exchange.in_flight_orders[order_id],
                request_call=order_request)

            create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp,
                             create_event.timestamp)
            self.assertEqual(self.trading_pair, create_event.trading_pair)
            self.assertEqual(OrderType.LIMIT, create_event.type)
            self.assertEqual(Decimal("100"), create_event.amount)
            self.assertEqual(Decimal("10000"), create_event.price)
            self.assertEqual(order_id, create_event.order_id)
            self.assertEqual(str(self.expected_exchange_order_id),
                             create_event.exchange_order_id)
            self.assertEqual(leverage, create_event.leverage)
            self.assertEqual(PositionAction.CLOSE.value, create_event.position)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Created {OrderType.LIMIT.name} {TradeType.BUY.name} order {order_id} for "
                    f"{Decimal('100.000000')} to {PositionAction.CLOSE.name} a {self.trading_pair} position "
                    f"at {Decimal('10000.0000')}."
                )
            )

        @aioresponses()
        def test_create_order_to_close_long_position(self, mock_api):
            self._simulate_trading_rules_initialized()
            request_sent_event = asyncio.Event()
            self.exchange._set_current_timestamp(1640780000)

            url = self.order_creation_url
            creation_response = self.order_creation_request_successful_mock_response

            mock_api.post(url,
                          body=json.dumps(creation_response),
                          callback=lambda *args, **kwargs: request_sent_event.set())
            leverage = 5
            self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
            order_id = self.place_sell_order(position_action=PositionAction.CLOSE)
            self.async_run_with_timeout(request_sent_event.wait())

            order_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(order_request)
            self.assertIn(order_id, self.exchange.in_flight_orders)
            self.validate_order_creation_request(
                order=self.exchange.in_flight_orders[order_id],
                request_call=order_request)

            create_event: SellOrderCreatedEvent = self.sell_order_created_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
            self.assertEqual(self.trading_pair, create_event.trading_pair)
            self.assertEqual(OrderType.LIMIT, create_event.type)
            self.assertEqual(Decimal("100"), create_event.amount)
            self.assertEqual(Decimal("10000"), create_event.price)
            self.assertEqual(order_id, create_event.order_id)
            self.assertEqual(str(self.expected_exchange_order_id), create_event.exchange_order_id)
            self.assertEqual(leverage, create_event.leverage)
            self.assertEqual(PositionAction.CLOSE.value, create_event.position)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"Created {OrderType.LIMIT.name} {TradeType.SELL.name} order {order_id} for "
                    f"{Decimal('100.000000')} to {PositionAction.CLOSE.name} a {self.trading_pair} position "
                    f"at {Decimal('10000.0000')}."
                )
            )

        @aioresponses()
        def test_update_order_status_when_filled(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)
            request_sent_event = asyncio.Event()

            leverage = 2
            self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
            self.exchange.start_tracking_order(
                order_id=self.client_order_id_prefix + "1",
                exchange_order_id=self.exchange_order_id_prefix + "1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                price=Decimal("10000"),
                amount=Decimal("1"),
                position_action=PositionAction.OPEN,
            )
            order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

            urls = self.configure_completely_filled_order_status_response(
                order=order,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set())

            if self.is_order_fill_http_update_included_in_status_update:
                trade_url = self.configure_full_fill_trade_response(
                    order=order,
                    mock_api=mock_api)
            else:
                # If the fill events will not be requested with the order status, we need to manually set the event
                # to allow the ClientOrderTracker to process the last status update
                order.completely_filled_event.set()
            self.async_run_with_timeout(self.exchange._update_order_status())
            # Execute one more synchronization to ensure the async task that processes the update is finished
            self.async_run_with_timeout(request_sent_event.wait())

            for url in (urls if isinstance(urls, list) else [urls]):
                order_status_request = self._all_executed_requests(mock_api, url)[0]
                self.validate_auth_credentials_present(order_status_request)
                self.validate_order_status_request(order=order, request_call=order_status_request)

            self.async_run_with_timeout(order.wait_until_completely_filled())
            self.assertTrue(order.is_done)

            if self.is_order_fill_http_update_included_in_status_update:
                self.assertTrue(order.is_filled)

                if trade_url:
                    trades_request = self._all_executed_requests(mock_api, trade_url)[0]
                    self.validate_auth_credentials_present(trades_request)
                    self.validate_trades_request(
                        order=order,
                        request_call=trades_request)

                fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
                self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
                self.assertEqual(order.client_order_id, fill_event.order_id)
                self.assertEqual(order.trading_pair, fill_event.trading_pair)
                self.assertEqual(order.trade_type, fill_event.trade_type)
                self.assertEqual(order.order_type, fill_event.order_type)
                self.assertEqual(order.price, fill_event.price)
                self.assertEqual(order.amount, fill_event.amount)
                self.assertEqual(self.expected_fill_fee, fill_event.trade_fee)
                self.assertEqual(leverage, fill_event.leverage)
                self.assertEqual(PositionAction.OPEN.value, fill_event.position)

            buy_event: BuyOrderCompletedEvent = self.buy_order_completed_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, buy_event.timestamp)
            self.assertEqual(order.client_order_id, buy_event.order_id)
            self.assertEqual(order.base_asset, buy_event.base_asset)
            self.assertEqual(order.quote_asset, buy_event.quote_asset)
            self.assertEqual(
                order.amount if self.is_order_fill_http_update_included_in_status_update else Decimal(0),
                buy_event.base_asset_amount)
            self.assertEqual(
                order.amount * order.price
                if self.is_order_fill_http_update_included_in_status_update
                else Decimal(0),
                buy_event.quote_asset_amount)
            self.assertEqual(order.order_type, buy_event.order_type)
            self.assertEqual(order.exchange_order_id, buy_event.exchange_order_id)
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"BUY order {order.client_order_id} completely filled."
                )
            )

        @aioresponses()
        def test_user_stream_update_for_order_full_fill(self, mock_api):
            self.exchange._set_current_timestamp(1640780000)
            leverage = 2
            self.exchange._perpetual_trading.set_leverage(self.trading_pair, leverage)
            self.exchange.start_tracking_order(
                order_id=self.client_order_id_prefix + "1",
                exchange_order_id=self.exchange_order_id_prefix + "1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.SELL,
                price=Decimal("10000"),
                amount=Decimal("1"),
                position_action=PositionAction.OPEN,
            )
            order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

            order_event = self.order_event_for_full_fill_websocket_update(order=order)
            trade_event = self.trade_event_for_full_fill_websocket_update(order=order)
            expected_unrealized_pnl = 12
            position_event = self.position_event_for_full_fill_websocket_update(
                order=order, unrealized_pnl=expected_unrealized_pnl
            )

            mock_queue = AsyncMock()
            event_messages = []
            if trade_event:
                event_messages.append(trade_event)
            if order_event:
                event_messages.append(order_event)
            if position_event:
                event_messages.append(position_event)
            event_messages.append(asyncio.CancelledError)
            mock_queue.get.side_effect = event_messages
            self.exchange._user_stream_tracker._user_stream = mock_queue

            if self.is_order_fill_http_update_executed_during_websocket_order_event_processing:
                self.configure_full_fill_trade_response(
                    order=order,
                    mock_api=mock_api)

            try:
                self.async_run_with_timeout(self.exchange._user_stream_event_listener())
            except asyncio.CancelledError:
                pass
            # Execute one more synchronization to ensure the async task that processes the update is finished
            self.async_run_with_timeout(order.wait_until_completely_filled())

            fill_event: OrderFilledEvent = self.order_filled_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, fill_event.timestamp)
            self.assertEqual(order.client_order_id, fill_event.order_id)
            self.assertEqual(order.trading_pair, fill_event.trading_pair)
            self.assertEqual(order.trade_type, fill_event.trade_type)
            self.assertEqual(order.order_type, fill_event.order_type)
            self.assertEqual(order.price, fill_event.price)
            self.assertEqual(order.amount, fill_event.amount)
            expected_fee = self.expected_fill_fee
            self.assertEqual(expected_fee, fill_event.trade_fee)
            self.assertEqual(leverage, fill_event.leverage)
            self.assertEqual(PositionAction.OPEN.value, fill_event.position)

            sell_event: SellOrderCompletedEvent = self.sell_order_completed_logger.event_log[0]
            self.assertEqual(self.exchange.current_timestamp, sell_event.timestamp)
            self.assertEqual(order.client_order_id, sell_event.order_id)
            self.assertEqual(order.base_asset, sell_event.base_asset)
            self.assertEqual(order.quote_asset, sell_event.quote_asset)
            self.assertEqual(order.amount, sell_event.base_asset_amount)
            self.assertEqual(order.amount * fill_event.price, sell_event.quote_asset_amount)
            self.assertEqual(order.order_type, sell_event.order_type)
            self.assertEqual(order.exchange_order_id, sell_event.exchange_order_id)
            self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
            self.assertTrue(order.is_filled)
            self.assertTrue(order.is_done)

            self.assertTrue(
                self.is_logged(
                    "INFO",
                    f"SELL order {order.client_order_id} completely filled."
                )
            )

            self.assertEqual(1, len(self.exchange.account_positions))

            position: Position = self.exchange.account_positions[self.trading_pair]
            self.assertEqual(self.trading_pair, position.trading_pair)
            self.assertEqual(PositionSide.SHORT, position.position_side)
            self.assertEqual(expected_unrealized_pnl, position.unrealized_pnl)
            self.assertEqual(fill_event.price, position.entry_price)
            self.assertEqual(-fill_event.amount, position.amount)
            self.assertEqual(leverage, position.leverage)

        def test_supported_position_modes(self):
            supported_modes = self.exchange.supported_position_modes()
            self.assertEqual(self.expected_supported_position_modes, supported_modes)

        @aioresponses()
        def test_set_position_mode_failure(self, mock_api):
            request_sent_event = asyncio.Event()
            _, error_msg = self.configure_failed_set_position_mode(
                position_mode=PositionMode.HEDGE,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set(),
            )
            self.exchange.set_position_mode(PositionMode.HEDGE)
            self.async_run_with_timeout(request_sent_event.wait())

            self.assertTrue(
                self.is_logged(
                    log_level="NETWORK",
                    message=f"Error switching {self.trading_pair} mode to {PositionMode.HEDGE}: {error_msg}"
                )
            )

        @aioresponses()
        def test_set_position_mode_success(self, mock_api):
            request_sent_event = asyncio.Event()
            self.configure_successful_set_position_mode(
                position_mode=PositionMode.HEDGE,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set(),
            )
            self.exchange.set_position_mode(PositionMode.HEDGE)
            self.async_run_with_timeout(request_sent_event.wait())

            self.assertTrue(
                self.is_logged(
                    log_level="DEBUG",
                    message=f"Position mode switched to {PositionMode.HEDGE}.",
                )
            )

            request_sent_event.clear()
            self.configure_successful_set_position_mode(
                position_mode=PositionMode.ONEWAY,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set(),
            )
            self.exchange.set_position_mode(PositionMode.ONEWAY)
            self.async_run_with_timeout(request_sent_event.wait())

            self.assertTrue(
                self.is_logged(
                    log_level="DEBUG",
                    message=f"Position mode switched to {PositionMode.ONEWAY}.",
                )
            )

        @aioresponses()
        def test_set_leverage_failure(self, mock_api):
            request_sent_event = asyncio.Event()
            target_leverage = 2
            _, message = self.configure_failed_set_leverage(
                leverage=target_leverage,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set(),
            )
            self.exchange.set_leverage(trading_pair=self.trading_pair, leverage=target_leverage)
            self.async_run_with_timeout(request_sent_event.wait())

            self.assertTrue(
                self.is_logged(
                    log_level="NETWORK",
                    message=f"Error setting leverage {target_leverage} for {self.trading_pair}: {message}",
                )
            )

        @aioresponses()
        def test_set_leverage_success(self, mock_api):
            request_sent_event = asyncio.Event()
            target_leverage = 2
            self.configure_successful_set_leverage(
                leverage=target_leverage,
                mock_api=mock_api,
                callback=lambda *args, **kwargs: request_sent_event.set(),
            )
            self.exchange.set_leverage(trading_pair=self.trading_pair, leverage=target_leverage)
            self.async_run_with_timeout(request_sent_event.wait())

            self.assertTrue(
                self.is_logged(
                    log_level="INFO",
                    message=f"Leverage for {self.trading_pair} successfully set to {target_leverage}.",
                )
            )

        @aioresponses()
        @patch("asyncio.Queue.get")
        def test_listen_for_funding_info_update_initializes_funding_info(self, mock_api, mock_queue_get):
            url = self.funding_info_url

            response = self.funding_info_mock_response
            mock_api.get(url, body=json.dumps(response))

            event_messages = [asyncio.CancelledError]
            mock_queue_get.side_effect = event_messages

            try:
                self.async_run_with_timeout(self.exchange._listen_for_funding_info())
            except asyncio.CancelledError:
                pass

            funding_info: FundingInfo = self.exchange.get_funding_info(self.trading_pair)

            self.assertEqual(self.trading_pair, funding_info.trading_pair)
            self.assertEqual(self.target_funding_info_index_price, funding_info.index_price)
            self.assertEqual(self.target_funding_info_mark_price, funding_info.mark_price)
            self.assertEqual(
                self.target_funding_info_next_funding_utc_timestamp, funding_info.next_funding_utc_timestamp
            )
            self.assertEqual(self.target_funding_info_rate, funding_info.rate)

        @aioresponses()
        @patch("asyncio.Queue.get")
        def test_listen_for_funding_info_update_updates_funding_info(self, mock_api, mock_queue_get):
            url = self.funding_info_url

            response = self.funding_info_mock_response
            mock_api.get(url, body=json.dumps(response))

            funding_info_event = self.funding_info_event_for_websocket_update()

            event_messages = [funding_info_event, asyncio.CancelledError]
            mock_queue_get.side_effect = event_messages

            try:
                self.async_run_with_timeout(
                    self.exchange._listen_for_funding_info())
            except asyncio.CancelledError:
                pass

            self.assertEqual(1, self.exchange._perpetual_trading.funding_info_stream.qsize())  # rest in OB DS tests

        @aioresponses()
        def test_funding_payment_polling_loop_sends_update_event(self, mock_api):
            def callback(*args, **kwargs):
                request_sent_event.set()

            self._simulate_trading_rules_initialized()
            request_sent_event = asyncio.Event()
            url = self.funding_payment_url

            async def run_test():
                response = self.empty_funding_payment_mock_response
                mock_api.get(url, body=json.dumps(response), callback=callback)
                _ = asyncio.create_task(self.exchange._funding_payment_polling_loop())

                # Allow task to start - on first pass no event is emitted (initialization)
                await asyncio.sleep(0.1)
                self.assertEqual(0, len(self.funding_payment_logger.event_log))

                response = self.funding_payment_mock_response
                mock_api.get(url, body=json.dumps(response), callback=callback, repeat=True)

                request_sent_event.clear()
                self.exchange._funding_fee_poll_notifier.set()
                await request_sent_event.wait()
                self.assertEqual(1, len(self.funding_payment_logger.event_log))

                request_sent_event.clear()
                self.exchange._funding_fee_poll_notifier.set()
                await request_sent_event.wait()

            self.async_run_with_timeout(run_test())

            self.assertEqual(1, len(self.funding_payment_logger.event_log))
            funding_event: FundingPaymentCompletedEvent = self.funding_payment_logger.event_log[0]
            self.assertEqual(self.target_funding_payment_timestamp, funding_event.timestamp)
            self.assertEqual(self.exchange.name, funding_event.market)
            self.assertEqual(self.trading_pair, funding_event.trading_pair)
            self.assertEqual(self.target_funding_payment_payment_amount, funding_event.amount)
            self.assertEqual(self.target_funding_payment_funding_rate, funding_event.funding_rate)

        @abstractmethod
        def test_get_buy_and_sell_collateral_tokens(self):
            raise NotImplementedError
