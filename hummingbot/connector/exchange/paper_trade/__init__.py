from typing import List, Callable
from hummingbot.client.config.config_helpers import get_connector_class
from hummingbot.connector.exchange.paper_trade.market_config import MarketConfig
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import PaperTradeExchange
from hummingbot.client.settings import CONNECTOR_SETTINGS


def get_order_book_tracker_class(connector_name: str) -> Callable:
    conn_setting = CONNECTOR_SETTINGS[connector_name]
    module_name = f"{conn_setting.base_name()}_order_book_tracker"
    class_name = "".join([o.capitalize() for o in module_name.split("_")])
    try:
        mod = __import__(f'hummingbot.connector.{conn_setting.type.name.lower()}.{conn_setting.base_name()}.'
                         f'{module_name}',
                         fromlist=[class_name])
        return getattr(mod, class_name)
    except Exception:
        pass
    raise Exception(f"Connector {connector_name} OrderBookTracker class not found")


def create_paper_trade_market(exchange_name: str, trading_pairs: List[str]):
    obt_class = get_order_book_tracker_class(exchange_name)
    conn_setting = CONNECTOR_SETTINGS[exchange_name]
    obt_params = {"trading_pairs": trading_pairs}
    return PaperTradeExchange(obt_class(**conn_setting.add_domain_parameter(obt_params)),
                              MarketConfig.default_config(),
                              get_connector_class(exchange_name))
