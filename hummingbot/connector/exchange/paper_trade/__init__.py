from typing import List, Callable
from hummingbot.client.config.config_helpers import get_connector_class
from hummingbot.connector.exchange.paper_trade.market_config import MarketConfig
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import PaperTradeExchange


def get_order_book_tracker_class(connector_name: str) -> Callable:
    module_name = f"{connector_name}_order_book_tracker"
    class_name = "".join([o.capitalize() for o in module_name.split("_")])
    try:
        mod = __import__(f'hummingbot.connector.exchange.{connector_name}.{module_name}',
                         fromlist=[class_name])
        return getattr(mod, class_name)
    except Exception:
        pass
    raise Exception(f"Connector {connector_name} OrderBookTracker class not found")


def create_paper_trade_market(exchange_name: str, trading_pairs: List[str]):
    order_book_tracker = get_order_book_tracker_class(exchange_name)
    return PaperTradeExchange(order_book_tracker(trading_pairs=trading_pairs),
                              MarketConfig.default_config(),
                              get_connector_class(exchange_name))
