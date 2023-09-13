from enum import Enum


class PolkadexOrderBookEvent(int, Enum):
    OrderBookDataSourceUpdateEvent = 904
    PublicTradeEvent = 905
