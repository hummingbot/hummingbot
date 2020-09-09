from typing import List

from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_order_book_tracker import BambooRelayOrderBookTracker
from hummingbot.connector.exchange.binance.binance_order_book_tracker import BinanceOrderBookTracker
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from hummingbot.connector.exchange.huobi.huobi_market import HuobiMarket
from hummingbot.connector.exchange.huobi.huobi_order_book_tracker import HuobiOrderBookTracker
from hummingbot.connector.exchange.paper_trade.market_config import MarketConfig
from hummingbot.connector.exchange.paper_trade.paper_trade_market import PaperTradeMarket
from hummingbot.connector.exchange.radar_relay.radar_relay_market import RadarRelayMarket
from hummingbot.connector.exchange.radar_relay.radar_relay_order_book_tracker import RadarRelayOrderBookTracker
from hummingbot.connector.exchange.dolomite.dolomite_order_book_tracker import DolomiteOrderBookTracker
from hummingbot.connector.exchange.dolomite.dolomite_market import DolomiteMarket

from hummingbot.connector.exchange.bamboo_relay.bamboo_relay_market import BambooRelayMarket
from hummingbot.connector.exchange.binance.binance_market import BinanceMarket
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_market import CoinbaseProMarket

from hummingbot.connector.exchange.bittrex.bittrex_market import BittrexOrderBookTracker, BittrexMarket
from hummingbot.connector.exchange.liquid.liquid_market import LiquidOrderBookTracker, LiquidMarket
from hummingbot.connector.exchange.kucoin.kucoin_market import KucoinOrderBookTracker, KucoinMarket
from hummingbot.connector.exchange.kraken.kraken_market import KrakenOrderBookTracker, KrakenMarket
from hummingbot.connector.exchange.crypto_com.crypto_com_exchange import CryptoComOrderBookTracker, CryptoComExchange

ORDER_BOOK_TRACKER_CLASS = {
    "binance": BinanceOrderBookTracker,
    "coinbase_pro": CoinbaseProOrderBookTracker,
    "bamboo_relay": BambooRelayOrderBookTracker,
    "radar_relay": RadarRelayOrderBookTracker,
    "huobi": HuobiOrderBookTracker,
    "bittrex": BittrexOrderBookTracker,
    "dolomite": DolomiteOrderBookTracker,
    "liquid": LiquidOrderBookTracker,
    "kucoin": KucoinOrderBookTracker,
    "kraken": KrakenOrderBookTracker,
    "crypto_com": CryptoComOrderBookTracker
}


MARKET_CLASSES = {
    "binance": BinanceMarket,
    "coinbase_pro": CoinbaseProMarket,
    "bamboo_relay": BambooRelayMarket,
    "radar_relay": RadarRelayMarket,
    "huobi": HuobiMarket,
    "bittrex": BittrexMarket,
    "dolomite": DolomiteMarket,
    "liquid": LiquidMarket,
    "kucoin": KucoinMarket,
    "kraken": KrakenMarket,
    "crypto_com": CryptoComExchange
}


def create_paper_trade_market(exchange_name: str, trading_pairs: List[str]):
    if exchange_name not in MARKET_CLASSES:
        raise Exception(f"Market {exchange_name.upper()} is not supported with paper trading mode.")
    order_book_tracker = ORDER_BOOK_TRACKER_CLASS[exchange_name]

    return PaperTradeMarket(order_book_tracker(trading_pairs=trading_pairs),
                            MarketConfig.default_config(),
                            MARKET_CLASSES[exchange_name]
                            )
