from typing import Dict, Tuple, Type

from hummingbot.core.data_type.order_book_row import OrderBookRow

OrderBookAsksBidsType: Type = Dict[str, Tuple[Tuple[OrderBookRow], ...]]
