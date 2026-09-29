import unittest
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock

import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_derivative import BybitPerpetualDerivative
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType


class BybitPerpetualMissingRateLimitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.calls: List[Dict[str, Any]] = []

    def _connector(self, trading_pairs: Optional[List[str]] = None) -> BybitPerpetualDerivative:
        connector = BybitPerpetualDerivative(
            bybit_perpetual_api_key="someKey",
            bybit_perpetual_secret_key="someSecret",
            trading_pairs=list(trading_pairs or []),
        )
        connector.add_trading_pair = AsyncMock(side_effect=AssertionError("add_trading_pair"))
        connector.start_network = AsyncMock(side_effect=AssertionError("start_network"))
        return connector

    def _install_rest(
        self,
        connector: BybitPerpetualDerivative,
        response: Any = None,
        error: Optional[Exception] = None,
    ) -> None:
        async def execute_request(*args, **kwargs):
            self.calls.append(kwargs)
            limit_id = kwargs["throttler_limit_id"]
            card = connector._throttler._id_to_limit_map.get(limit_id)
            self.assertIsNotNone(card)
            self.assertIsNotNone(card.weight)
            async with connector._throttler.execute_task(limit_id=limit_id):
                pass
            if error is not None:
                raise error
            return response if response is not None else {"retCode": 0, "retMsg": "OK", "result": {"list": []}}

        rest_assistant = Mock()
        rest_assistant.execute_request = execute_request
        connector._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)

    def _limit_id(self, endpoint: Dict[str, str], trading_pair: str) -> str:
        return web_utils.get_pair_specific_limit_id(endpoint[CONSTANTS.LINEAR_MARKET], trading_pair)

    def _bucket_id(self, base_limit_id: str, trading_pair: str) -> str:
        return web_utils.get_pair_specific_limit_id(base_limit_id, trading_pair)

    async def test_appended_pair_position_read_reaches_request_once(self):
        connector = self._connector()
        trading_pair = "NEO-USDT"
        connector._trading_pairs.append(trading_pair)
        self._install_rest(connector)

        await connector._api_get(
            path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
            params={"category": "linear", "symbol": "NEOUSDT"},
            is_auth_required=True,
            trading_pair=trading_pair,
        )

        position_id = self._limit_id(CONSTANTS.GET_POSITIONS_PATH_URL, trading_pair)
        self.assertEqual(1, len(self.calls))
        self.assertEqual(position_id, self.calls[0]["throttler_limit_id"])
        self.assertIn(position_id, connector._throttler._id_to_limit_map)
        self.assertIsNotNone(connector._throttler._id_to_limit_map[position_id].weight)
        self.assertIn(
            self._bucket_id(CONSTANTS.LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID, trading_pair),
            connector._throttler._id_to_limit_map,
        )
        self.assertNotIn(
            self._bucket_id(CONSTANTS.NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID, trading_pair),
            connector._throttler._id_to_limit_map,
        )
        connector.add_trading_pair.assert_not_called()
        connector.start_network.assert_not_called()

    async def test_buy_for_late_pair_submits_one_order(self):
        connector = self._connector()
        trading_pair = "NEO-USDT"
        order_id = "only-one"
        self._install_rest(connector, response={"retCode": 0, "retMsg": "OK", "result": {"orderId": order_id}})
        connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="NEOUSDT")

        exchange_order_id, _timestamp = await connector._place_order(
            order_id="client-1",
            trading_pair=trading_pair,
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.MARKET,
            price=Decimal("1"),
            position_action=PositionAction.OPEN,
        )

        create_id = self._limit_id(CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL, trading_pair)
        self.assertEqual(order_id, exchange_order_id)
        self.assertEqual(1, len(self.calls))
        self.assertEqual(create_id, self.calls[0]["throttler_limit_id"])
        self.assertIn(create_id, connector._throttler._id_to_limit_map)
        self.assertIn(
            self._bucket_id(CONSTANTS.LINEAR_PRIVATE_BUCKET_100_LIMIT_ID, trading_pair),
            connector._throttler._id_to_limit_map,
        )

    async def test_request_error_is_not_retried(self):
        connector = self._connector()
        trading_pair = "NEO-USDT"
        self._install_rest(connector, error=RuntimeError("exchange down"))

        with self.assertRaises(RuntimeError):
            await connector._api_post(
                path_url=CONSTANTS.PLACE_ACTIVE_ORDER_PATH_URL,
                data={"category": "linear", "symbol": "NEOUSDT", "side": "Buy"},
                is_auth_required=True,
                trading_pair=trading_pair,
            )

        self.assertEqual(1, len(self.calls))

    async def test_unknown_limit_id_does_not_invent_a_card_or_call_exchange(self):
        connector = self._connector()
        trading_pair = "NEO-USDT"
        self._install_rest(connector)
        unknown_id = "not-a-real-card"

        with self.assertRaises(ValueError):
            await connector._api_get(
                path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
                is_auth_required=True,
                trading_pair=trading_pair,
                limit_id=unknown_id,
            )

        self.assertEqual(0, len(self.calls))
        self.assertNotIn(unknown_id, connector._throttler._id_to_limit_map)
        self.assertIn(self._limit_id(CONSTANTS.GET_POSITIONS_PATH_URL, trading_pair), connector._throttler._id_to_limit_map)

    async def test_new_pair_does_not_drop_existing_cards(self):
        connector = self._connector(["BTC-USDT"])
        sentinel_id = "sentinel-card"
        connector._throttler.add_rate_limits([RateLimit(limit_id=sentinel_id, limit=1, time_interval=1)])
        connector._throttler.set_rate_limits = Mock(side_effect=AssertionError("set_rate_limits"))
        self._install_rest(connector)
        btc_id = self._limit_id(CONSTANTS.GET_POSITIONS_PATH_URL, "BTC-USDT")

        await connector._api_get(
            path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
            is_auth_required=True,
            trading_pair="NEO-USDT",
        )

        self.assertIn(btc_id, connector._throttler._id_to_limit_map)
        self.assertIn(sentinel_id, connector._throttler._id_to_limit_map)
        self.assertEqual(1, len(self.calls))

    async def test_inverse_pair_uses_non_linear_bucket(self):
        connector = self._connector()
        trading_pair = "BTC-USD"
        self._install_rest(connector)

        await connector._api_get(
            path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
            is_auth_required=True,
            trading_pair=trading_pair,
        )

        position_id = web_utils.get_pair_specific_limit_id(
            CONSTANTS.GET_POSITIONS_PATH_URL[CONSTANTS.NON_LINEAR_MARKET],
            trading_pair,
        )
        self.assertEqual(position_id, self.calls[0]["throttler_limit_id"])
        self.assertIn(
            self._bucket_id(CONSTANTS.NON_LINEAR_PRIVATE_BUCKET_120_B_LIMIT_ID, trading_pair),
            connector._throttler._id_to_limit_map,
        )
        self.assertNotIn(
            self._bucket_id(CONSTANTS.LINEAR_PRIVATE_BUCKET_120_A_LIMIT_ID, trading_pair),
            connector._throttler._id_to_limit_map,
        )

    async def test_request_without_pair_does_not_invent_a_pair_card(self):
        connector = self._connector()
        self._install_rest(connector)
        before = set(connector._throttler._id_to_limit_map)

        await connector._api_get(
            path_url=CONSTANTS.GET_WALLET_BALANCE_PATH_URL,
            params={"accountType": "UNIFIED"},
            is_auth_required=True,
        )

        self.assertEqual(1, len(self.calls))
        self.assertEqual(before, set(connector._throttler._id_to_limit_map))
        self.assertEqual(
            CONSTANTS.GET_WALLET_BALANCE_PATH_URL[CONSTANTS.LINEAR_MARKET],
            self.calls[0]["throttler_limit_id"],
        )

    async def test_second_request_does_not_duplicate_the_card(self):
        connector = self._connector()
        trading_pair = "NEO-USDT"
        self._install_rest(connector)

        await connector._api_get(
            path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
            is_auth_required=True,
            trading_pair=trading_pair,
        )
        await connector._api_get(
            path_url=CONSTANTS.GET_POSITIONS_PATH_URL,
            is_auth_required=True,
            trading_pair=trading_pair,
        )

        position_id = self._limit_id(CONSTANTS.GET_POSITIONS_PATH_URL, trading_pair)
        ids = [rate_limit.limit_id for rate_limit in connector._throttler._rate_limits]
        self.assertEqual(1, ids.count(position_id))
        self.assertEqual(2, len(self.calls))
