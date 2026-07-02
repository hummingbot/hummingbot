import unittest
from decimal import Decimal

from hummingbot.connector.exchange.twofinance.twofinance_exchange import TwoFinanceExchange
from hummingbot.connector.exchange.twofinance.twofinance_matchengine_schemas import MatchEngineEvent
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class TwoFinanceExchangeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.exchange = TwoFinanceExchange(
            twofinance_matchengine_bearer_token="token",
            twofinance_engine_id="engine-btc-usdt",
            twofinance_wallet_id=7,
            trading_pairs=["BTC-USDT"],
            trading_required=False,
            ack_timeout=0,
        )
        self.exchange._symbol_metadata["BTC-USDT"] = {"symbol_id": 1, "symbol": "BTC-USDT"}

    async def test_build_order_command_maps_hummingbot_order(self):
        self.exchange._symbol_metadata["BTC-USDT"]["exchange_symbol"] = "BTC/USDT"
        command = await self.exchange._build_order_command(
            order_id="HBOT-2F-1",
            trading_pair="BTC-USDT",
            amount=Decimal("0.25"),
            trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT_MAKER,
            price=Decimal("100"),
            time_in_force=None,
        )

        payload = command.to_payload()
        self.assertEqual(payload["side"], "SELL")
        self.assertEqual(payload["order_type"], "LIMIT")
        self.assertNotIn("time_in_force", payload)
        self.assertEqual(payload["symbol_id"], 1)
        self.assertEqual(payload["market"], "BTC-USDT")

    async def test_format_trading_rules(self):
        rules = await self.exchange._format_trading_rules(
            {
                "data": {
                    "trading_rules": {
                        "BTC-USDT": {
                            "symbol": "BTC-USDT",
                            "min_order_size": "0.001",
                            "tick_size": "0.01",
                            "step_size": "0.0001",
                            "min_notional": "10",
                        }
                    }
                }
            }
        )

        self.assertEqual(rules[0].trading_pair, "BTC-USDT")
        self.assertEqual(rules[0].min_order_size, Decimal("0.001"))
        self.assertEqual(rules[0].min_price_increment, Decimal("0.01"))
        self.assertEqual(rules[0].min_base_amount_increment, Decimal("0.0001"))
        self.assertEqual(rules[0].min_notional_size, Decimal("10"))

    async def test_format_trading_rules_normalizes_exchange_pair(self):
        rules = await self.exchange._format_trading_rules(
            {
                "data": {
                    "trading_rules": [
                        {
                            "name": "BTC/USDT",
                            "min_order_size": "0.001",
                            "tick_size": "0.01",
                            "step_size": "0.0001",
                            "min_notional": "10",
                        }
                    ]
                }
            }
        )

        self.assertEqual(rules[0].trading_pair, "BTC-USDT")

    def test_initialize_trading_pair_symbols_normalizes_state_api_symbols(self):
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(
            {
                "data": {
                    "symbols": [
                        {
                            "symbol_id": 1,
                            "name": "BTC/USDT",
                        }
                    ]
                }
            }
        )

        self.assertEqual(self.exchange._symbol_metadata["BTC-USDT"]["exchange_symbol"], "BTC/USDT")

    def test_order_update_from_event(self):
        event = MatchEngineEvent.from_payload(
            {
                "schema": "matchengine.event.v1",
                "sequence": 1,
                "event_id": "engine:1",
                "event_type": "ORDER_ACCEPTED",
                "symbol_id": 1,
                "market": "BTC-USDT",
                "payload": {"client_order_id": "HBOT-2F-1", "order_id": 99, "order_status": 1},
            }
        )

        update = self.exchange._order_update_from_event(event)

        self.assertEqual(update.client_order_id, "HBOT-2F-1")
        self.assertEqual(update.exchange_order_id, "99")
        self.assertEqual(update.new_state, OrderState.OPEN)

    def test_trade_update_from_event_uses_exchange_order_mapping(self):
        order = InFlightOrder(
            client_order_id="HBOT-2F-1",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            exchange_order_id="99",
            creation_timestamp=1,
        )
        self.exchange._order_tracker.start_tracking_order(order)
        self.exchange._matchengine_client.orders_by_exchange_id["99"] = "HBOT-2F-1"
        event = MatchEngineEvent.from_payload(
            {
                "schema": "matchengine.event.v1",
                "sequence": 2,
                "event_id": "engine:2",
                "event_type": "TRADE_EXECUTED",
                "symbol_id": 1,
                "market": "BTC-USDT",
                "payload": {
                    "trade_id": "t-1",
                    "taker_order_id": 99,
                    "price": "100",
                    "quantity": "0.5",
                    "fee_asset": "USDT",
                    "fee_amount": "0.01",
                },
            }
        )

        trade_update = self.exchange._trade_update_from_event(event)

        self.assertEqual(trade_update.client_order_id, "HBOT-2F-1")
        self.assertEqual(trade_update.fill_base_amount, Decimal("0.5"))
        self.assertEqual(trade_update.fill_quote_amount, Decimal("50.0"))
        self.assertEqual(trade_update.fee.flat_fees[0].token, "USDT")
        self.assertEqual(trade_update.fee.flat_fees[0].amount, Decimal("0.01"))


if __name__ == "__main__":
    unittest.main()
