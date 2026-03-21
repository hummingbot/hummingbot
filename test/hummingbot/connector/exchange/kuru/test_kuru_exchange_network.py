import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.kuru import kuru_constants as CONSTANTS
from hummingbot.connector.exchange.kuru.kuru_exchange import NetworkStatus, OrderType, TradeType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee

from .test_kuru_exchange_base import KuruExchangeTestBase


class TestKuruExchangeNetwork(KuruExchangeTestBase, IsolatedAsyncioTestCase):

    def test_supported_order_types(self):
        self.assertEqual(
            [OrderType.LIMIT, OrderType.LIMIT_MAKER],
            self.connector.supported_order_types(),
        )

    def test_initialize_trading_pair_symbols_maps_identity(self):
        self.connector._set_trading_pair_symbol_map(None)
        self.connector._initialize_trading_pair_symbols_from_exchange_info({})

        self.assertTrue(self.connector.trading_pair_symbol_map_ready())

    async def test_check_network_returns_connected_for_healthy_client(self):
        self.client.is_healthy.return_value = True

        status = await self.connector.check_network()

        self.assertEqual(NetworkStatus.CONNECTED, status)

    async def test_check_network_returns_not_connected_for_unhealthy_client(self):
        self.client.is_healthy.return_value = False

        status = await self.connector.check_network()

        self.assertEqual(NetworkStatus.NOT_CONNECTED, status)

    async def test_check_network_uses_default_api_url_when_client_not_started(self):
        self.connector._client = None
        requested_urls = []

        response = MagicMock(status=200)
        response_cm = AsyncMock()
        response_cm.__aenter__.return_value = response
        response_cm.__aexit__.return_value = None

        session = MagicMock()
        session.get.side_effect = lambda url, timeout=None: requested_urls.append(url) or response_cm
        session_cm = AsyncMock()
        session_cm.__aenter__.return_value = session
        session_cm.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=session_cm):
            status = await self.connector.check_network()

        self.assertEqual(NetworkStatus.CONNECTED, status)
        self.assertEqual([f"{CONSTANTS.DEFAULT_KURU_API_URL.rstrip('/')}/healthz"], requested_urls)

    @patch("hummingbot.connector.exchange.kuru.kuru_exchange.asyncio.ensure_future")
    @patch("hummingbot.connector.exchange.kuru.kuru_exchange.KuruClient.create", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.kuru.kuru_exchange.get_market_config")
    async def test_start_sdk_uses_defaults_and_starts_client(self, get_market_config_mock, create_mock, ensure_future_mock):
        get_market_config_mock.return_value = self.market_config

        fake_client = self.client
        create_mock.return_value = fake_client

        self.connector._update_trading_rules = AsyncMock()
        self.connector._cancel_orders_without_kuru_mapping_on_startup = AsyncMock()

        fake_task = MagicMock()

        def close_and_return_task(coro):
            coro.close()
            return fake_task

        ensure_future_mock.side_effect = close_and_return_task

        await self.connector._start_sdk()

        self.assertIs(fake_client, self.connector._client)
        self.assertIs(fake_task, self.connector._sdk_health_task)
        get_market_config_mock.assert_called_once_with(self.market_address, rpc_url=None)
        create_mock.assert_awaited_once()
        fake_client.set_order_callback.assert_called_once()
        fake_client.set_orderbook_callback.assert_called_once()
        fake_client.start.assert_awaited_once()
        fake_client.subscribe_to_orderbook.assert_awaited_once()
        self.connector._update_trading_rules.assert_awaited_once()
        self.connector._cancel_orders_without_kuru_mapping_on_startup.assert_awaited_once()

        connection_config = create_mock.await_args.kwargs["connection_config"]
        self.assertEqual(CONSTANTS.DEFAULT_RPC_URL, connection_config.rpc_url)
        self.assertEqual(CONSTANTS.DEFAULT_RPC_WS_URL, connection_config.rpc_ws_url)
        self.assertEqual(CONSTANTS.DEFAULT_KURU_WS_URL, connection_config.kuru_ws_url)
        self.assertEqual(CONSTANTS.DEFAULT_KURU_API_URL, connection_config.kuru_api_url)

    async def test_on_sdk_order_event_enqueues_order(self):
        sdk_order = self.make_sdk_order()

        await self.connector._on_sdk_order_event(sdk_order)

        queued = self.connector._sdk_order_event_queue.get_nowait()
        self.assertIs(sdk_order, queued)

    async def test_on_sdk_orderbook_event_updates_last_trade_price_and_enqueues_update(self):
        update = SimpleNamespace(
            b=[(1.1, 2.2)],
            a=[(1.2, 3.3)],
            events=[SimpleNamespace(e="Trade", p="12.5")],
        )

        await self.connector._on_sdk_orderbook_event(update)

        self.assertEqual(12.5, self.connector.last_traded_prices[self.trading_pair])
        self.assertIs(update, self.connector.sdk_orderbook_queue.get_nowait())

    async def test_on_sdk_orderbook_event_tolerates_missing_events(self):
        update = SimpleNamespace(b=[(1.1, 2.2)], a=[(1.2, 3.3)], events=None)

        await self.connector._on_sdk_orderbook_event(update)

        self.assertEqual({}, self.connector.last_traded_prices)
        self.assertIs(update, self.connector.sdk_orderbook_queue.get_nowait())

    # ------------------------------------------------------------------
    # stop_network
    # ------------------------------------------------------------------

    async def test_stop_network_no_tasks_no_client_calls_super(self):
        self.connector._sdk_health_task = None
        self.connector._sdk_start_task = None
        self.connector._client = None

        # Should complete without raising
        await self.connector.stop_network()

        # Client remains None
        self.assertIsNone(self.connector._client)

    async def test_stop_network_cancels_health_and_start_tasks(self):
        health_task = MagicMock()
        start_task = MagicMock()
        self.connector._sdk_health_task = health_task
        self.connector._sdk_start_task = start_task
        self.connector._client = None

        await self.connector.stop_network()

        health_task.cancel.assert_called_once()
        start_task.cancel.assert_called_once()
        self.assertIsNone(self.connector._sdk_health_task)
        self.assertIsNone(self.connector._sdk_start_task)

    async def test_stop_network_with_active_orders_cancels_before_stopping_client(self):
        self.connector._sdk_health_task = None
        self.connector._sdk_start_task = None
        # Set up an active order so len(active_orders) > 0
        order = self.make_order(client_order_id="active-1")
        self.connector._order_tracker.active_orders = {order.client_order_id: order}
        self.connector._cancel_all_active_orders_for_market = AsyncMock()

        await self.connector.stop_network()

        self.connector._cancel_all_active_orders_for_market.assert_awaited_once()
        self.client.stop.assert_awaited_once()
        self.assertIsNone(self.connector._client)

    # ------------------------------------------------------------------
    # _update_trading_rules
    # ------------------------------------------------------------------

    async def test_update_trading_rules_skips_when_market_config_is_none(self):
        self.connector._market_config = None
        self.connector._trading_rules.clear()

        await self.connector._update_trading_rules()

        # No rules should have been built
        self.assertEqual({}, self.connector._trading_rules)

    async def test_update_trading_rules_builds_correct_rule_from_market_config(self):
        # market_config is already set to self.market_config by setUp
        self.connector._trading_rules.clear()

        await self.connector._update_trading_rules()

        self.assertIn(self.trading_pair, self.connector._trading_rules)
        rule = self.connector._trading_rules[self.trading_pair]
        self.assertEqual(self.expected_trading_rule.min_price_increment, rule.min_price_increment)
        self.assertEqual(self.expected_trading_rule.min_base_amount_increment, rule.min_base_amount_increment)
        self.assertTrue(rule.supports_limit_orders)
        self.assertFalse(rule.supports_market_orders)
        self.assertEqual("USDC", rule.buy_order_collateral_token)
        self.assertEqual("MON", rule.sell_order_collateral_token)

    # ------------------------------------------------------------------
    # _format_trading_rules
    # ------------------------------------------------------------------

    async def test_format_trading_rules_returns_empty_list_when_no_market_config(self):
        self.connector._market_config = None
        self.connector._trading_rules.clear()

        result = await self.connector._format_trading_rules({})

        self.assertEqual([], result)

    async def test_format_trading_rules_calls_update_and_returns_rules(self):
        self.connector._update_trading_rules = AsyncMock(
            side_effect=lambda: self.connector._trading_rules.__setitem__(
                self.trading_pair, self.expected_trading_rule
            )
        )

        result = await self.connector._format_trading_rules({})

        self.connector._update_trading_rules.assert_awaited_once()
        self.assertEqual([self.expected_trading_rule], result)

    # ------------------------------------------------------------------
    # _get_fee
    # ------------------------------------------------------------------

    def test_get_fee_returns_zero_for_maker_limit_order(self):
        fee = self.connector._get_fee(
            base_currency="MON",
            quote_currency="USDC",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
        )

        self.assertIsInstance(fee, AddedToCostTradeFee)
        self.assertEqual(Decimal("0"), fee.percent)

    def test_get_fee_returns_taker_fee_for_non_limit_order(self):
        fee = self.connector._get_fee(
            base_currency="MON",
            quote_currency="USDC",
            order_type=OrderType.MARKET,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            is_maker=False,
        )

        expected_fee = Decimal(str(CONSTANTS.DEFAULT_TAKER_FEE_BPS)) / Decimal("10000")
        self.assertIsInstance(fee, AddedToCostTradeFee)
        self.assertEqual(expected_fee, fee.percent)

    # ------------------------------------------------------------------
    # _get_rpc_server_time
    # ------------------------------------------------------------------

    async def test_get_rpc_server_time_returns_block_timestamp_in_ms(self):
        # hex(1700000000) == '0x655cc640'
        hex_timestamp = hex(1700000000)
        rpc_response = {"result": {"timestamp": hex_timestamp}}

        resp_mock = AsyncMock()
        resp_mock.json = AsyncMock(return_value=rpc_response)
        resp_cm = AsyncMock()
        resp_cm.__aenter__.return_value = resp_mock
        resp_cm.__aexit__.return_value = None

        session_mock = MagicMock()
        session_mock.post = MagicMock(return_value=resp_cm)
        session_cm = AsyncMock()
        session_cm.__aenter__.return_value = session_mock
        session_cm.__aexit__.return_value = None

        with patch("aiohttp.ClientSession", return_value=session_cm):
            result = await self.connector._get_rpc_server_time()

        expected = float(1700000000 * 1e3)
        self.assertAlmostEqual(expected, result)

    # ------------------------------------------------------------------
    # _update_time_synchronizer
    # ------------------------------------------------------------------

    async def test_update_time_synchronizer_calls_time_sync_update(self):
        self.connector._time_synchronizer = MagicMock()
        self.connector._time_synchronizer.update_server_time_offset_with_time_provider = AsyncMock()
        self.connector._get_rpc_server_time = AsyncMock(return_value=1700000000000.0)

        await self.connector._update_time_synchronizer()

        self.connector._time_synchronizer.update_server_time_offset_with_time_provider.assert_awaited_once()

    async def test_update_time_synchronizer_suppresses_exception_when_pass_on_error_true(self):
        self.connector._time_synchronizer = MagicMock()
        self.connector._time_synchronizer.update_server_time_offset_with_time_provider = AsyncMock(
            side_effect=RuntimeError("RPC unavailable")
        )
        self.connector._get_rpc_server_time = AsyncMock(return_value=0.0)

        # Should not raise when pass_on_non_cancelled_error=True
        await self.connector._update_time_synchronizer(pass_on_non_cancelled_error=True)

    # ------------------------------------------------------------------
    # _sdk_health_monitor_loop
    # ------------------------------------------------------------------

    async def test_sdk_health_monitor_loop_restarts_sdk_when_unhealthy(self):
        self.client.is_healthy.return_value = False
        self.connector._restart_sdk = AsyncMock()
        self.connector._expire_ghost_orders = MagicMock()

        # Run loop in background; advance past the asyncio.sleep(30) by mocking it
        sleep_call_count = 0

        async def fast_sleep(seconds):
            nonlocal sleep_call_count
            sleep_call_count += 1
            if sleep_call_count >= 2:
                raise asyncio.CancelledError

        with patch("asyncio.sleep", side_effect=fast_sleep):
            try:
                await self.connector._sdk_health_monitor_loop()
            except asyncio.CancelledError:
                pass

        self.connector._restart_sdk.assert_awaited()

    # ------------------------------------------------------------------
    # _restart_sdk
    # ------------------------------------------------------------------

    async def test_restart_sdk_stops_old_client_and_starts_new_one(self):
        self.connector._start_sdk = AsyncMock()

        await self.connector._restart_sdk()

        self.client.stop.assert_awaited_once()
        self.assertIsNone(self.connector._client)
        self.connector._start_sdk.assert_awaited_once()
