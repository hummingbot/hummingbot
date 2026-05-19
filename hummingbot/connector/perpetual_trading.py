import asyncio
import copy
import logging
import time
import warnings
from collections import defaultdict
from typing import Callable, Coroutine, Dict, List, Optional

from hummingbot.connector.derivative.position import Position
from hummingbot.connector.utils import split_hb_trading_pair
from hummingbot.core.data_type.common import PositionMode, PositionSide
from hummingbot.core.data_type.funding_info import FundingInfo, FundingInfoUpdate
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class PerpetualTrading:
    """Keeps perpetual trading state.

    Enhanced with funding info staleness detection and REST API fallback.
    """

    _logger: Optional[HummingbotLogger] = None

    # Staleness detection constants (mirrors order_book_tracker pattern)
    FUNDING_STALENESS_THRESHOLD: float = 180.0  # 3 min (same as trade prices)
    FUNDING_REST_COOLDOWN: float = 30.0          # 30s between REST calls per pair
    FUNDING_CHECK_INTERVAL: float = 5.0          # Check every 5 seconds
    FUNDING_LOG_INTERVAL: float = 60.0           # Throttle stale warnings to 1/min

    def __init__(self, trading_pairs: List[str], exchange_name: str = ""):
        self._account_positions: Dict[str, Position] = {}
        self._position_mode: PositionMode = PositionMode.ONEWAY
        self._leverage: Dict[str, int] = defaultdict(lambda: 1)
        self._trading_pairs = trading_pairs
        self._exchange_name = exchange_name

        self._funding_info: Dict[str, FundingInfo] = {}
        self._funding_payment_span: List[int] = [0, 0]
        self._funding_info_stream = asyncio.Queue()

        self._funding_info_updater_task: Optional[asyncio.Task] = None

        # Staleness detection (new)
        self._funding_staleness_task: Optional[asyncio.Task] = None
        self._rest_refresh_callback: Optional[
            Callable[[str], Coroutine]
        ] = None
        self._last_staleness_log_times: Dict[str, float] = {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(
                HummingbotLogger.logger_name_for_class(cls)
            )
        return cls._logger

    @property
    def account_positions(self) -> Dict[str, Position]:
        """
        Returns a dictionary of current active open positions
        """
        return self._account_positions

    @property
    def funding_info(self) -> Dict[str, FundingInfo]:
        """
        The funding information per trading pair.
        """
        return copy.deepcopy(self._funding_info)

    @property
    def funding_info_stream(self) -> asyncio.Queue:
        """
        The stream to which to supply funding info updates to be processed by the class.
        """
        return self._funding_info_stream

    def set_position(self, pos_key: str, position: Position):
        self.logger().debug(f"Setting position {pos_key} to {Position}")
        self._account_positions[pos_key] = position

    def remove_position(self, post_key: str) -> Optional[Position]:
        return self._account_positions.pop(post_key, None)

    def initialize_funding_info(self, funding_info: FundingInfo):
        """
        Initializes a single trading pair funding information.
        """
        self._funding_info[funding_info.trading_pair] = funding_info

    def add_trading_pair(self, trading_pair: str):
        """
        Adds a trading pair to tracked list.
        """
        if trading_pair not in self._trading_pairs:
            self._trading_pairs.append(trading_pair)

    def remove_trading_pair(self, trading_pair: str):
        """
        Removes a trading pair and cleans up related data.
        """
        if trading_pair in self._trading_pairs:
            self._trading_pairs.remove(trading_pair)
        self._funding_info.pop(trading_pair, None)
        if trading_pair in self._leverage:
            del self._leverage[trading_pair]

    def is_funding_info_initialized(self) -> bool:
        return all(
            trading_pair in self._funding_info
            for trading_pair in self._trading_pairs
        )

    def set_rest_refresh_callback(
        self, callback: Callable[[str], Coroutine]
    ) -> None:
        """Set the async callback for REST API funding info refresh.

        Called by connector overrides to provide the REST fallback function.
        The callback receives a trading_pair string and should fetch fresh
        funding info via REST API and call initialize_funding_info().
        """
        self._rest_refresh_callback = callback

    def start(self):
        """Starts the funding info updater and staleness detection."""
        self.stop()
        self._funding_info_updater_task = safe_ensure_future(
            self._funding_info_updater()
        )
        self._funding_staleness_task = safe_ensure_future(
            self._funding_info_staleness_loop()
        )

    def stop(self):
        """
        Stops the funding info updating and staleness async tasks.
        """
        if self._funding_info_updater_task is not None:
            self._funding_info_updater_task.cancel()
            self._funding_info_updater_task = None
        if self._funding_staleness_task is not None:
            self._funding_staleness_task.cancel()
            self._funding_staleness_task = None
        self._funding_info.clear()

    def position_key(
        self,
        trading_pair: str,
        side: PositionSide = None,
        mode: PositionMode = None,
    ) -> str:
        """
        Returns a key to a position in account_positions. On OneWay position mode this is the trading pair.
        On Hedge position mode this is a combination of trading pair and position side
        :param trading_pair: The market trading pair
        :param side: The position side (long or short)
        :return: A key to the position in account_positions dictionary
        """
        pos_key = ""
        if mode is not None:
            pos_key = (
                f"{trading_pair}{side.name}"
                if mode == PositionMode.HEDGE
                else trading_pair
            )
        else:
            pos_key = (
                f"{trading_pair}{side.name}"
                if self._position_mode == PositionMode.HEDGE
                else trading_pair
            )
        return pos_key

    def get_position(
        self, trading_pair: str, side: PositionSide = None
    ) -> Optional[Position]:
        """
        Returns an active position if exists, otherwise returns None
        :param trading_pair: The market trading pair
        :param side: The position side (long or short)
        :return: A position from account_positions or None
        """
        return self.account_positions.get(
            self.position_key(trading_pair, side), None
        )

    @property
    def funding_payment_span(self) -> List[int]:
        """
        Time span(in seconds) before and after funding period when exchanges consider active positions eligible for
        funding payment.
        :return: a list of seconds (before and after)
        """
        return self._funding_payment_span

    @property
    def position_mode(self) -> PositionMode:
        return self._position_mode

    def set_position_mode(self, value: PositionMode):
        """
        Sets position mode for perpetual trading, a child class might need to override this to set position mode on
        the exchange
        :param value: the position mode
        """
        self._position_mode = value

    def get_leverage(self, trading_pair: str) -> int:
        """
        Gets leverage level of a particular market
        :param trading_pair: the market trading pair
        :return: leverage level
        """
        return self._leverage[trading_pair]

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        """
        Sets leverage level, e.g. 2x, 10x, etc..
        A child class may need to override this to set leverage level on the exchange
        :param trading_pair: the market trading pair
        :param leverage: leverage to be used
        """
        self._leverage[trading_pair] = leverage

    def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Returns funding information
        :param trading_pair: the market trading pair
        :return: funding info
        """
        return self._funding_info[trading_pair]

    async def _funding_info_updater(self):
        while True:
            try:
                funding_info_message: FundingInfoUpdate = (
                    await self._funding_info_stream.get()
                )
                trading_pair = funding_info_message.trading_pair
                if trading_pair not in self._funding_info:
                    self.logger().debug(
                        f"Received funding info update for "
                        f"uninitialized pair {trading_pair}, skipping."
                    )
                    continue
                funding_info = self._funding_info[trading_pair]
                funding_info.update(funding_info_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error updating funding info.",
                    exc_info=True,
                )

    async def _funding_info_staleness_loop(self):
        """Check for stale funding info and trigger REST refresh.

        Mirrors order_book_tracker._update_last_trade_prices_loop:
        - Detects when WS updates stop arriving (3 min threshold)
        - Triggers REST API fallback with rate limiting (30s cooldown)
        - Logs staleness warnings throttled to 1/min per pair
        """
        # Wait for initial funding info to populate
        await asyncio.sleep(60)

        while True:
            try:
                await self._check_funding_staleness()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in funding staleness check",
                    exc_info=True,
                )
            await asyncio.sleep(self.FUNDING_CHECK_INTERVAL)

    async def _check_funding_staleness(self):
        """Check all pairs and REST-refresh any that are stale."""
        if not self._rest_refresh_callback:
            return

        now = time.perf_counter()

        for trading_pair, fi in list(self._funding_info.items()):
            if not self._is_stale_and_refreshable(fi, now):
                continue
            self._log_staleness_warning(trading_pair, fi, now)
            await self._do_rest_refresh(trading_pair, now)

    def _is_stale_and_refreshable(
        self, fi: FundingInfo, now: float
    ) -> bool:
        """True if funding info is stale AND REST cooldown has elapsed."""
        ws_age = now - fi.last_ws_update_time
        rest_age = now - fi.last_rest_refresh_time
        is_stale = ws_age > self.FUNDING_STALENESS_THRESHOLD
        rest_ready = rest_age > self.FUNDING_REST_COOLDOWN
        return is_stale and rest_ready

    def _log_staleness_warning(
        self, trading_pair: str, fi: FundingInfo, now: float
    ) -> None:
        """Log a throttled staleness warning."""
        last_log = self._last_staleness_log_times.get(trading_pair, 0)
        if now - last_log < self.FUNDING_LOG_INTERVAL:
            return
        self._last_staleness_log_times[trading_pair] = now
        ws_age = now - fi.last_ws_update_time
        tag = f"[{self._exchange_name}] " if self._exchange_name else ""
        self.logger().warning(
            f"{tag}Funding info stale for {trading_pair} "
            f"(no WS update for {ws_age:.0f}s, "
            f"threshold: {self.FUNDING_STALENESS_THRESHOLD:.0f}s). "
            f"Triggering REST refresh."
        )

    async def _do_rest_refresh(
        self, trading_pair: str, now: float
    ) -> None:
        """Call REST refresh callback and update refresh timestamp."""
        try:
            await self._rest_refresh_callback(trading_pair)
            # Set rest refresh time on the (potentially new) object
            if trading_pair in self._funding_info:
                self._funding_info[
                    trading_pair
                ].last_rest_refresh_time = now
        except Exception:
            self.logger().error(
                f"REST refresh failed for {trading_pair}",
                exc_info=True,
            )

    def get_buy_collateral_token(self, trading_pair: str) -> str:
        warnings.warn(
            "This method is replaced by "
            "PerpetualDerivativePyBase.get_buy_collateral_token, "
            "and will be removed once all perpetual connectors "
            "are updated to the latest standards.",
            DeprecationWarning,
            stacklevel=2,
        )
        _, quote = split_hb_trading_pair(trading_pair)
        return quote

    def get_sell_collateral_token(self, trading_pair: str) -> str:
        warnings.warn(
            "This method is replaced by "
            "PerpetualDerivativePyBase.get_sell_collateral_token, "
            "and will be removed once all perpetual connectors "
            "are updated to the latest standards.",
            DeprecationWarning,
            stacklevel=2,
        )
        _, quote = split_hb_trading_pair(trading_pair)
        return quote
