"""
Bluefin SDK data source wrapper.

This module wraps the BluefinProSdk to provide a clean interface
for the connector to interact with the Bluefin exchange.
"""
# pyright: reportMissingTypeStubs=false

import asyncio
import logging
from decimal import Decimal
from types import TracebackType
from typing import Any, Dict, List, Optional, Type

# Bluefin SDK imports
try:
    from bluefin_pro_sdk import BluefinProSdk, Order, Environment
    from crypto_helpers.wallet import SuiWallet
    from openapi_client import CancelOrdersRequest
    from openapi_client.models.account_data_stream import AccountDataStream
    from openapi_client.models.market_data_stream_name import MarketDataStreamName
    from openapi_client.models.market_subscription_streams import MarketSubscriptionStreams
except ImportError as e:
    raise ImportError(
        "bluefin_pro_sdk is required for Bluefin connector. "
        "Please install it with: pip install bluefin-pro-sdk"
    ) from e

logger = logging.getLogger(__name__)


class BluefinDataSource:
    """
    Wrapper for BluefinProSdk that manages the SDK lifecycle and provides
    a clean interface for the connector.
    """

    def __init__(self, wallet_mnemonic: str, network: str = "MAINNET", debug: bool = False):
        """
        Initialize Bluefin data source.

        :param wallet_mnemonic: 24-word mnemonic phrase
        :param network: Network name ("MAINNET" or "STAGING")
        :param debug: Enable debug logging in SDK
        """
        self._wallet_mnemonic = wallet_mnemonic
        self._network = network
        self._debug = debug

        # SDK environment mapping
        self._env = Environment.PRODUCTION if network == "MAINNET" else Environment.STAGING

        # Create wallet and SDK client
        self._wallet = SuiWallet(mnemonic=wallet_mnemonic)
        self._client: Optional[BluefinProSdk] = None
        self._is_initialized = False

        # Symbol mapping: hummingbot (BTC-USD) <-> Bluefin (BTC-PERP)
        self._hb_to_bluefin: Dict[str, str] = {}

        # WebSocket listeners
        self._market_data_listener = None
        self._account_data_listener = None

        # Event queues for streaming data with category fan-out
        self._market_event_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._market_funding_event_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._market_order_book_event_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._market_trade_event_queue: asyncio.Queue[Any] = asyncio.Queue()

        self._account_event_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._account_order_event_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._account_trade_event_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._account_position_event_queue: asyncio.Queue[Any] = asyncio.Queue()
        self._account_balance_event_queue: asyncio.Queue[Any] = asyncio.Queue()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ):
        """Async context manager exit."""
        await self.shutdown()

    def _require_client(self) -> BluefinProSdk:
        if self._client is None:
            raise RuntimeError("Bluefin SDK client is not initialized")
        return self._client

    async def initialize(self):
        """Initialize the SDK client and login."""
        if self._is_initialized:
            return

        try:
            self._client = BluefinProSdk(
                sui_wallet=self._wallet,
                env=self._env,
                debug=self._debug
            )
            await self._require_client().init()
            self._is_initialized = True
            logger.info("Bluefin SDK initialized for network: %s", self._network)

            # Load exchange info to populate symbol mapping
            await self._load_exchange_info()

        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Failed to initialize Bluefin SDK: %s", e)
            raise

    async def shutdown(self):
        """Shutdown the SDK client and cleanup resources."""
        try:
            # Close WebSocket listeners
            if self._market_data_listener is not None:
                try:
                    market_listener: Any = self._market_data_listener
                    await market_listener.__aexit__(None, None, None)
                except (AttributeError, RuntimeError, TypeError) as e:
                    logger.error("Error closing market data listener: %s", e)
                self._market_data_listener = None

            if self._account_data_listener is not None:
                try:
                    account_listener: Any = self._account_data_listener
                    await account_listener.__aexit__(None, None, None)
                except (AttributeError, RuntimeError, TypeError) as e:
                    logger.error("Error closing account data listener: %s", e)
                self._account_data_listener = None

            # Close SDK client
            if self._client is not None:
                try:
                    client: Any = self._require_client()
                    await client.__aexit__(None, None, None)
                except (AttributeError, RuntimeError, TypeError) as e:
                    logger.error("Error closing SDK client: %s", e)
                self._client = None

            self._is_initialized = False
            logger.info("Bluefin SDK shutdown complete")

        except (RuntimeError, AttributeError, TypeError) as e:
            logger.error("Error during Bluefin SDK shutdown: %s", e)

    async def _load_exchange_info(self):
        """Load exchange info and build symbol mapping."""
        info = await self._require_client().exchange_data_api.get_exchange_info()
        for market in info.markets:
            # Bluefin uses "BTC-PERP" format, hummingbot uses "BTC-USD"
            bluefin_symbol = market.symbol
            base = bluefin_symbol.split("-")[0]  # Extract "BTC" from "BTC-PERP"
            hb_symbol = f"{base}-USD"  # Create "BTC-USD"
            self._hb_to_bluefin[hb_symbol] = bluefin_symbol

        logger.info("Loaded %s trading pairs from Bluefin", len(self._hb_to_bluefin))

    def hb_to_bluefin_symbol(self, hb_symbol: str) -> str:
        """Convert hummingbot symbol to Bluefin symbol."""
        return self._hb_to_bluefin.get(hb_symbol, hb_symbol)

    def bluefin_to_hb_symbol(self, bluefin_symbol: str) -> str:
        """Convert Bluefin symbol to hummingbot symbol."""
        for hb_symbol, bf_symbol in self._hb_to_bluefin.items():
            if bf_symbol == bluefin_symbol:
                return hb_symbol
        return bluefin_symbol

    @staticmethod
    def to_e9(value: Decimal) -> str:
        """Convert Decimal to e9 string format."""
        return str(int(value * Decimal("1e9")))

    @staticmethod
    def from_e9(e9_str: str) -> Decimal:
        """Convert e9 string to Decimal."""
        return Decimal(e9_str) / Decimal("1e9")

    # ======================
    # Exchange Data API
    # ======================

    async def get_exchange_info(self) -> Any:
        """Get exchange information including markets and assets."""
        return await self._require_client().exchange_data_api.get_exchange_info()

    async def get_market_ticker(self, symbol: str) -> Any:
        """Get market ticker for a symbol."""
        bluefin_symbol = self.hb_to_bluefin_symbol(symbol)
        return await self._require_client().exchange_data_api.get_market_ticker(bluefin_symbol)

    async def get_all_market_tickers(self) -> Any:
        """Get all market tickers."""
        return await self._require_client().exchange_data_api.get_all_market_ticker()

    async def get_orderbook(self, symbol: str) -> Any:
        """Get orderbook depth for a symbol."""
        bluefin_symbol = self.hb_to_bluefin_symbol(symbol)
        return await self._require_client().exchange_data_api.get_orderbook_depth(bluefin_symbol)

    async def get_funding_rate_history(self, symbol: str, limit: int = 1) -> Any:
        """Get funding rate history for a symbol."""
        del limit
        bluefin_symbol = self.hb_to_bluefin_symbol(symbol)
        return await self._require_client().exchange_data_api.get_funding_rate_history(
            symbol=bluefin_symbol
        )

    # ======================
    # Account Data API
    # ======================

    async def get_account(self, account_address: Optional[str] = None) -> Any:
        """Get account details including balance and positions."""
        return await self._require_client().account_data_api.get_account_details(
            account_address=account_address
        )

    async def get_account_trades(
        self,
        symbol: str,
        start_time_at_millis: Optional[int] = None,
        end_time_at_millis: Optional[int] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
    ) -> Any:
        """Get account trade history."""
        bluefin_symbol = self.hb_to_bluefin_symbol(symbol)
        return await self._require_client().account_data_api.get_account_trades(
            symbol=bluefin_symbol,
            start_time_at_millis=start_time_at_millis,
            end_time_at_millis=end_time_at_millis,
            limit=limit,
            page=page,
        )

    async def get_account_funding_rate_history(
        self,
        account_address: Optional[str] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None
    ) -> Any:
        """Get account funding rate history."""
        return await self._require_client().account_data_api.get_account_funding_rate_history(
            account_address=account_address,
            limit=limit,
            page=page
        )

    # ======================
    # Trading API
    # ======================

    async def get_open_orders(self, symbol: str) -> Any:
        """Get open orders for a symbol."""
        bluefin_symbol = self.hb_to_bluefin_symbol(symbol)
        return await self._require_client().get_open_orders(bluefin_symbol)

    async def place_order(self, order: Order) -> Any:
        """
        Place an order.

        :param order: Order object from bluefin_pro_sdk
        :return: CreateOrderResponse with order_hash
        """
        # Convert symbol if needed
        order.symbol = self.hb_to_bluefin_symbol(order.symbol)
        return await self._require_client().create_order(order)

    async def cancel_order(self, symbol: str, order_hash: Optional[str] = None) -> Any:
        """
        Cancel order(s) for a symbol.

        :param symbol: Trading pair symbol
        :param order_hash: Specific order hash to cancel (None cancels all)
        :return: CancelOrdersResponse
        """
        bluefin_symbol = self.hb_to_bluefin_symbol(symbol)
        request = CancelOrdersRequest.model_construct(
            symbol=bluefin_symbol,
            order_hashes=[order_hash] if order_hash is not None else None,
        )
        return await self._require_client().cancel_order(request)

    async def cancel_all_orders(self, symbol: str) -> Any:
        """Cancel all orders for a symbol."""
        return await self.cancel_order(symbol, order_hash=None)

    async def set_leverage(self, symbol: str, leverage: Decimal) -> Any:
        """
        Set leverage for a trading pair.

        :param symbol: Trading pair symbol
        :param leverage: Leverage value (e.g., Decimal("10") for 10x)
        :return: Response from update_leverage
        """
        bluefin_symbol = self.hb_to_bluefin_symbol(symbol)
        leverage_e9 = self.to_e9(leverage)
        return await self._require_client().update_leverage(
            symbol=bluefin_symbol,
            leverage_e9=leverage_e9
        )

    # ======================
    # WebSocket Streaming
    # ======================

    async def create_market_data_stream(self, symbols: List[str]) -> None:
        """
        Create market data stream listener for given symbols.

        :param symbols: List of trading pair symbols (hummingbot format)
        """
        if self._market_data_listener is not None:
            logger.warning("Market data stream already exists")
            return

        async def handler(msg: Any):
            """Handler for market data events."""
            event_name = type(msg).__name__
            await self._market_event_queue.put(msg)
            if event_name in {"OraclePriceUpdate", "MarkPriceUpdate"}:
                await self._market_funding_event_queue.put(msg)
            if event_name in {"OrderbookDiffDepthUpdate", "OrderbookPartialDepthUpdate"}:
                await self._market_order_book_event_queue.put(msg)
            if event_name == "RecentTradesUpdates":
                await self._market_trade_event_queue.put(msg)

        self._market_data_listener = await self._require_client().create_market_data_stream_listener(
            handler=handler
        )

        # Subscribe to streams for each symbol
        subscriptions: List[Any] = []
        for symbol in symbols:
            bluefin_symbol = self.hb_to_bluefin_symbol(symbol)
            subscriptions.append(
                MarketSubscriptionStreams(
                    symbol=bluefin_symbol,
                    streams=[
                        MarketDataStreamName.ORACLE_PRICE,
                        MarketDataStreamName.MARK_PRICE,
                        MarketDataStreamName.DIFF_DEPTH_500_MS,
                        MarketDataStreamName.PARTIAL_DEPTH_5,
                        MarketDataStreamName.RECENT_TRADE,
                    ]
                )
            )

        await self._market_data_listener.subscribe(subscriptions)
        logger.info("Market data stream created for %s symbols", len(symbols))

    async def create_account_data_stream(self) -> None:
        """Create account data stream listener."""
        if self._account_data_listener is not None:
            logger.warning("Account data stream already exists")
            return

        async def handler(msg: Any):
            """Handler for account data events."""
            event_name = type(msg).__name__
            await self._account_event_queue.put(msg)
            if event_name == "AccountOrderUpdate":
                await self._account_order_event_queue.put(msg)
            elif event_name == "AccountTradeUpdate":
                await self._account_trade_event_queue.put(msg)
            elif event_name == "AccountPositionUpdate":
                await self._account_position_event_queue.put(msg)
            elif event_name == "AccountUpdate":
                await self._account_balance_event_queue.put(msg)

        self._account_data_listener = await self._require_client().create_account_data_stream_listener(
            handler=handler
        )

        # Subscribe to all account streams
        await self._account_data_listener.subscribe([
            AccountDataStream.ACCOUNTORDERUPDATE,
            AccountDataStream.ACCOUNTTRADEUPDATE,
            AccountDataStream.ACCOUNTPOSITIONUPDATE,
            AccountDataStream.ACCOUNTUPDATE,
            AccountDataStream.ACCOUNTTRANSACTIONUPDATE,
        ])
        logger.info("Account data stream created")

    async def get_market_event(self) -> Any:
        """Get next market event from queue (blocking)."""
        return await self._market_event_queue.get()

    async def get_market_funding_event(self) -> Any:
        """Get next funding-related market event."""
        return await self._market_funding_event_queue.get()

    async def get_market_order_book_event(self) -> Any:
        """Get next order book-related market event."""
        return await self._market_order_book_event_queue.get()

    async def get_market_trade_event(self) -> Any:
        """Get next trade-related market event."""
        return await self._market_trade_event_queue.get()

    async def get_account_event(self) -> Any:
        """Get next account event from queue (blocking)."""
        return await self._account_event_queue.get()

    async def get_account_order_event(self) -> Any:
        """Get next account order event."""
        return await self._account_order_event_queue.get()

    async def get_account_trade_event(self) -> Any:
        """Get next account trade event."""
        return await self._account_trade_event_queue.get()

    async def get_account_position_event(self) -> Any:
        """Get next account position event."""
        return await self._account_position_event_queue.get()

    async def get_account_balance_event(self) -> Any:
        """Get next account balance event."""
        return await self._account_balance_event_queue.get()

    # ======================
    # Helper Properties
    # ======================

    @property
    def is_initialized(self) -> bool:
        """Check if SDK is initialized."""
        return self._is_initialized

    @property
    def wallet_address(self) -> str:
        """Get wallet address."""
        return self._wallet.sui_address

    @property
    def trading_pair_symbol_map(self) -> Dict[str, str]:
        """Get the internal HB<->Bluefin trading pair map."""
        return self._hb_to_bluefin
