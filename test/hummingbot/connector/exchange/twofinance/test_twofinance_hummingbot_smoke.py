import os
import time
import unittest
from decimal import Decimal

from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.exchange.twofinance import twofinance_constants as CONSTANTS
from hummingbot.connector.exchange.twofinance.twofinance_exchange import TwoFinanceExchange
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder

RUN_SMOKE = os.getenv("TWO_FINANCE_RUN_HUMMINGBOT_SMOKE") == "1"


@unittest.skipUnless(RUN_SMOKE, "set TWO_FINANCE_RUN_HUMMINGBOT_SMOKE=1 to run the local 2Finance Hummingbot smoke")
class TwoFinanceHummingbotSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.exchange = TwoFinanceExchange(
            twofinance_matchengine_bearer_token=os.getenv("TWO_FINANCE_MATCHENGINE_BEARER_TOKEN", "valid-order-token"),
            twofinance_engine_id=os.getenv("TWO_FINANCE_MATCHENGINE_ENGINE_ID", "local-matchengine"),
            twofinance_wallet_id=int(os.getenv("TWO_FINANCE_MATCHENGINE_WALLET_ID", "1")),
            twofinance_state_api_url=os.getenv("TWO_FINANCE_STATE_API_URL", "http://127.0.0.1:11080/api/v1"),
            twofinance_matchengine_ws_url=os.getenv("TWO_FINANCE_MATCHENGINE_WS_URL", CONSTANTS.WSS_URL),
            trading_pairs=[os.getenv("TWO_FINANCE_TRADING_PAIR", "BTC-USDT")],
            trading_required=True,
            ack_timeout=float(os.getenv("TWO_FINANCE_MATCHENGINE_ACK_TIMEOUT", "5")),
        )

    async def asyncTearDown(self):
        await self.exchange._matchengine_client.close()
        await self.exchange._web_assistants_factory.close()

    async def test_connector_loads_market_data_places_and_cancels_order(self):
        settings = AllConnectorSettings.get_connector_settings()
        self.assertIn("twofinance", settings)
        self.assertIn("twofinance_testnet", settings)

        symbols = await self.exchange._api_get(path_url=CONSTANTS.SYMBOLS_PATH_URL)
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(symbols)
        self.assertEqual(self.exchange._symbol_metadata["BTC-USDT"]["exchange_symbol"], "BTC/USDT")

        rules_payload = await self.exchange._api_get(path_url=CONSTANTS.TRADING_RULES_PATH_URL)
        rules = await self.exchange._format_trading_rules(rules_payload)
        self.assertEqual(rules[0].trading_pair, "BTC-USDT")

        await self.exchange._update_balances()
        self.assertGreater(self.exchange.get_balance("USDT"), Decimal("0"))

        data_source = self.exchange._create_order_book_data_source()
        snapshot = await data_source._order_book_snapshot("BTC-USDT")
        self.assertEqual(snapshot.trading_pair, "BTC-USDT")
        self.assertGreater(len(snapshot.bids), 0)

        client_order_id = f"HBOT-2F-SMOKE-{int(time.time() * 1000)}"
        exchange_order_id, _ = await self.exchange._place_order(
            order_id=client_order_id,
            trading_pair="BTC-USDT",
            amount=Decimal(os.getenv("TWO_FINANCE_SMOKE_ORDER_AMOUNT", "1")),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal(os.getenv("TWO_FINANCE_SMOKE_ORDER_PRICE", "100")),
        )
        self.assertTrue(exchange_order_id)

        tracked_order = InFlightOrder(
            client_order_id=client_order_id,
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal(os.getenv("TWO_FINANCE_SMOKE_ORDER_AMOUNT", "1")),
            price=Decimal(os.getenv("TWO_FINANCE_SMOKE_ORDER_PRICE", "100")),
            exchange_order_id=str(exchange_order_id),
            creation_timestamp=self.exchange.current_timestamp,
        )
        self.assertTrue(await self.exchange._place_cancel(f"{client_order_id}-CANCEL", tracked_order))


if __name__ == "__main__":
    unittest.main()
