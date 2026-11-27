from typing import List

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow


class ReyaPerpetualOrderBook(OrderBook):
    """An order book that ignores depth updates no newer than its current snapshot.

    Reya's depth updates carry the absolute quantity of each level, so an update that predates the
    snapshot would restore an older quantity. The order book tracker can apply such updates: after a
    snapshot it replays its recent diffs, and it applies diffs queued before the first snapshot,
    without comparing update ids. The data source derives update ids from the server time of each
    book state, so comparing them here keeps only the updates that are newer than the snapshot.
    """

    def apply_diffs(self, bids: List[OrderBookRow], asks: List[OrderBookRow], update_id: int):
        if update_id <= self.snapshot_uid:
            return
        super().apply_diffs(bids, asks, update_id)
