from typing import List

from hummingbot.market.bamboo_relay.bamboo_relay_order_book_tracker import BambooRelayOrderBookTracker
from hummingbot.market.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.market.coinbase_pro.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from hummingbot.market.ddex.ddex_order_book_tracker import DDEXOrderBookTracker
from hummingbot.market.idex.idex_order_book_tracker import IDEXOrderBookTracker
from hummingbot.market.paper_trade.market_config import MarketConfig
from hummingbot.market.paper_trade.paper_trade_market import PaperTradeMarket
ORDER_BOOK_TRACKER_CLASS = {
    "binance": BinanceOrderBookTracker,
    "idex": IDEXOrderBookTracker,
    "ddex": DDEXOrderBookTracker,
    "coinbase_pro": CoinbaseProOrderBookTracker,
    "bamboo_relay": BambooRelayOrderBookTracker
}


def create_paper_trade_market(exchange_name: str, trading_pairs: List[str]):
    order_book_tracker = ORDER_BOOK_TRACKER_CLASS[exchange_name]
    return PaperTradeMarket(order_book_tracker(symbols=trading_pairs), MarketConfig.default_config())
