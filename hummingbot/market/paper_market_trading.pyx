from collections import deque
from cpython cimport PyObject
from cython.operator cimport (
    postincrement as inc,
    dereference as deref,
    address
)
from decimal import Decimal
from libcpp cimport bool as cppbool
from libcpp.vector cimport vector
import logging
import math
import random
from typing import (
    Dict,
    List,
)

from hummingbot.core.clock cimport Clock
from hummingbot.core.Utils cimport (
    getIteratorFromReverseIterator,
    reverse_iterator
)
from hummingbot.core.network_iterator import NetworkStatus

from hummingbot.core.event.events import (
    MarketEvent,
    WalletEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketReceivedAssetEvent,
    WalletReceivedAssetEvent,
    OrderBookEvent,
    OrderFilledEvent,
    OrderCancelledEvent,
    TradeType,
    TradeFee,
    OrderExpiredEvent,
)
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.data_type.limit_order cimport c_create_limit_order_from_cpp_limit_order
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.order_book cimport OrderBook
from hummingbot.core.data_type.order_expiration_entry cimport c_create_order_expiration_from_cpp_order_expiration
from hummingbot.market.market_base import (
    MarketBase,
    NaN
)
from hummingbot.core.event.events import OrderType

from hummingbot.wallet.wallet_base import WalletBase
from hummingbot.wallet.wallet_base cimport WalletBase
from .market_config import (
    MarketConfig,
    AssetType
)
from .market_account_manager_base cimport MarketAccountManagerBase
from .market_account_manager_base import MarketAccountManagerBase
from .order_book_loader_base import OrderBookLoaderBase
from .order_book_loader_base cimport OrderBookLoaderBase

s_logger = None