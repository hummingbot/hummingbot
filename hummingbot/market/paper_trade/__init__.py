from typing import List

from hummingbot.market.bamboo_relay.bamboo_relay_order_book_tracker import BambooRelayOrderBookTracker
from hummingbot.market.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.market.coinbase_pro.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from hummingbot.market.ddex.ddex_order_book_tracker import DDEXOrderBookTracker
from hummingbot.market.huobi.huobi_market import HuobiMarket
from hummingbot.market.huobi.huobi_order_book_tracker import HuobiOrderBookTracker
# from hummingbot.market.idex.idex_order_book_tracker import IDEXOrderBookTracker
from hummingbot.market.paper_trade.market_config import MarketConfig
from hummingbot.market.paper_trade.paper_trade_market import PaperTradeMarket
from hummingbot.market.radar_relay.radar_relay_market import RadarRelayMarket
from hummingbot.market.radar_relay.radar_relay_order_book_tracker import RadarRelayOrderBookTracker
from hummingbot.market.dolomite.dolomite_order_book_tracker import DolomiteOrderBookTracker
from hummingbot.market.dolomite.dolomite_market import DolomiteMarket

from hummingbot.market.bamboo_relay.bamboo_relay_market import BambooRelayMarket
from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket
from hummingbot.market.ddex.ddex_market import DDEXMarket
# from hummingbot.market.idex.idex_market import IDEXMarket

from hummingbot.market.bittrex.bittrex_market import BittrexOrderBookTracker, BittrexMarket
from hummingbot.market.bitcoin_com.bitcoin_com_market import BitcoinComOrderBookTracker, BitcoinComMarket
from hummingbot.market.liquid.liquid_market import LiquidOrderBookTracker, LiquidMarket

ORDER_BOOK_TRACKER_CLASS = {
    "binance": BinanceOrderBookTracker,
    "ddex": DDEXOrderBookTracker,
    "coinbase_pro": CoinbaseProOrderBookTracker,
    "bamboo_relay": BambooRelayOrderBookTracker,
    "radar_relay": RadarRelayOrderBookTracker,
    "huobi": HuobiOrderBookTracker,
    "bittrex": BittrexOrderBookTracker,
    "dolomite": DolomiteOrderBookTracker,
    "bitcoin_com": BitcoinComOrderBookTracker,
    "liquid": LiquidOrderBookTracker
}


MARKET_CLASSES = {
    "binance": BinanceMarket,
    "ddex": DDEXMarket,
    "coinbase_pro": CoinbaseProMarket,
    "bamboo_relay": BambooRelayMarket,
    "radar_relay": RadarRelayMarket,
    "huobi": HuobiMarket,
    "bittrex": BittrexMarket,
    "dolomite": DolomiteMarket,
    "bitcoin_com": BitcoinComMarket,
    "liquid": LiquidMarket
}


def create_paper_trade_market(exchange_name: str, trading_pairs: List[str]):
    if exchange_name not in MARKET_CLASSES:
        raise Exception(f"Market {exchange_name.upper()} is not supported with paper trading mode.")
    order_book_tracker = ORDER_BOOK_TRACKER_CLASS[exchange_name]

    return PaperTradeMarket(order_book_tracker(trading_pairs=trading_pairs),
                            MarketConfig.default_config(),
                            MARKET_CLASSES[exchange_name]
                            )
