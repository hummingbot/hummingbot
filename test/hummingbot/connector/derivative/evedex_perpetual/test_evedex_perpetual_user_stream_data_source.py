import asyncio
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth
from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_user_stream_data_source import (
    EvedexPerpetualUserStreamDataSource,
)


class EvedexPerpetualUserStreamDataSourceTests(TestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.domain = "evedex_perpetual"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        
        self.auth = MagicMock(spec=EvedexPerpetualAuth)
        self.auth.wallet_address = "0x1234567890abcdef"
        self.auth.get_ws_auth_payload = MagicMock(return_value={
            "walletAddress": "0x1234567890abcdef",
            "timestamp": 1234567890000,
            "signature": "0xsignature"
        })
        
        self.connector = MagicMock()
        self.api_factory = MagicMock()
        
        self.data_source = EvedexPerpetualUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=self.domain
        )
        
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_last_recv_time_no_assistant(self):
        """Test last recv time when no WebSocket assistant exists."""
        self.data_source._ws_assistant = None
        self.assertEqual(self.data_source.last_recv_time, 0)

    def test_last_recv_time_with_assistant(self):
        """Test last recv time with WebSocket assistant."""
        mock_ws = MagicMock()
        mock_ws.last_recv_time = 1234567890.0
        self.data_source._ws_assistant = mock_ws
        
        self.assertEqual(self.data_source.last_recv_time, 1234567890.0)

    def test_process_event_message_error(self):
        """Test handling of error event messages."""
        queue = asyncio.Queue()
        error_message = {
            "error": {
                "message": "Authentication failed"
            }
        }
        
        with self.assertRaises(IOError) as context:
            self.async_run_with_timeout(
                self.data_source._process_event_message(error_message, queue)
            )
        
        self.assertIn("Authentication failed", str(context.exception))

    def test_process_event_message_orders(self):
        """Test handling of order update messages."""
        queue = asyncio.Queue()
        order_message = {
            "push": {
                "channel": f"{CONSTANTS.WS_USER_ORDERS_CHANNEL}:0x1234567890abcdef",
                "pub": {
                    "data": {
                        "orderId": "12345",
                        "status": "filled"
                    }
                }
            }
        }
        
        self.async_run_with_timeout(
            self.data_source._process_event_message(order_message, queue)
        )
        
        self.assertFalse(queue.empty())
        queued_message = queue.get_nowait()
        self.assertEqual(queued_message, order_message)

    def test_process_event_message_trades(self):
        """Test handling of trade messages."""
        queue = asyncio.Queue()
        trade_message = {
            "push": {
                "channel": f"{CONSTANTS.WS_USER_TRADES_CHANNEL}:0x1234567890abcdef",
                "pub": {
                    "data": {
                        "tradeId": "67890",
                        "price": "50000"
                    }
                }
            }
        }
        
        self.async_run_with_timeout(
            self.data_source._process_event_message(trade_message, queue)
        )
        
        self.assertFalse(queue.empty())

    def test_process_event_message_positions(self):
        """Test handling of position update messages."""
        queue = asyncio.Queue()
        position_message = {
            "push": {
                "channel": f"{CONSTANTS.WS_USER_POSITIONS_CHANNEL}:0x1234567890abcdef",
                "pub": {
                    "data": {
                        "symbol": "BTCUSDT",
                        "size": "1.5"
                    }
                }
            }
        }
        
        self.async_run_with_timeout(
            self.data_source._process_event_message(position_message, queue)
        )
        
        self.assertFalse(queue.empty())

    def test_process_event_message_balance(self):
        """Test handling of balance update messages."""
        queue = asyncio.Queue()
        balance_message = {
            "push": {
                "channel": f"{CONSTANTS.WS_USER_BALANCE_CHANNEL}:0x1234567890abcdef",
                "pub": {
                    "data": {
                        "asset": "USDT",
                        "available": "10000"
                    }
                }
            }
        }
        
        self.async_run_with_timeout(
            self.data_source._process_event_message(balance_message, queue)
        )
        
        self.assertFalse(queue.empty())

    def test_process_event_message_unknown_channel(self):
        """Test that unknown channels are ignored."""
        queue = asyncio.Queue()
        unknown_message = {
            "push": {
                "channel": "unknown:channel",
                "pub": {
                    "data": {}
                }
            }
        }
        
        self.async_run_with_timeout(
            self.data_source._process_event_message(unknown_message, queue)
        )
        
        # Unknown channel messages should not be queued
        self.assertTrue(queue.empty())

    def test_heartbeat_interval(self):
        """Test heartbeat interval is correctly set."""
        self.assertEqual(
            EvedexPerpetualUserStreamDataSource.HEARTBEAT_TIME_INTERVAL,
            30.0
        )

    def test_listen_key_keep_alive_interval(self):
        """Test listen key keep alive interval."""
        self.assertEqual(
            EvedexPerpetualUserStreamDataSource.LISTEN_KEY_KEEP_ALIVE_INTERVAL,
            1800
        )
