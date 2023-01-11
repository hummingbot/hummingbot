import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from hummingbot.core.data_type.funding_info import FundingInfo
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource


class PerpetualAPIOrderBookDataSource(OrderBookTrackerDataSource, ABC):
    def __init__(self, trading_pairs: List[str]):
        super().__init__(trading_pairs)
        self._funding_info_messages_queue_key = "funding_info"

    @abstractmethod
    async def get_funding_info(self, trading_pair: str) -> FundingInfo:
        """
        Return the funding information for a single trading pair.
        """
        raise NotImplementedError

    async def listen_for_funding_info(self, output: asyncio.Queue):
        """
        Reads the funding info events queue and updates the local funding info information.
        """
        message_queue = self._message_queue[self._funding_info_messages_queue_key]
        while True:
            try:
                funding_info_event = await message_queue.get()
                await self._parse_funding_info_message(raw_message=funding_info_event, message_queue=output)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().exception("Unexpected error when processing public funding info updates from exchange")

    @abstractmethod
    async def _parse_funding_info_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        raise NotImplementedError

    def _get_messages_queue_keys(self) -> List[str]:
        return [
            self._snapshot_messages_queue_key,
            self._diff_messages_queue_key,
            self._trade_messages_queue_key,
            self._funding_info_messages_queue_key,
        ]
