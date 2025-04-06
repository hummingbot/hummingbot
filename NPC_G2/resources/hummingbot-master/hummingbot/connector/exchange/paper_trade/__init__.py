from typing import List

from hummingbot.client.config.config_helpers import ClientConfigAdapter, get_connector_class
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import PaperTradeExchange
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker


def get_order_book_tracker(connector_name: str, trading_pairs: List[str]) -> OrderBookTracker:
    conn_setting = AllConnectorSettings.get_connector_settings()[connector_name]
    try:
        connector_instance = conn_setting.non_trading_connector_instance_with_default_configuration(
            trading_pairs=trading_pairs)
        return connector_instance.order_book_tracker
    except Exception as exception:
        raise Exception(f"Connector {connector_name} OrderBookTracker class not found ({exception})")


def create_paper_trade_market(exchange_name: str, client_config_map: ClientConfigAdapter, trading_pairs: List[str]):
    tracker = get_order_book_tracker(connector_name=exchange_name, trading_pairs=trading_pairs)
    return PaperTradeExchange(client_config_map,
                              tracker,
                              get_connector_class(exchange_name),
                              exchange_name=exchange_name)
