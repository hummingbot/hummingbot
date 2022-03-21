import importlib
from typing import List

from hummingbot.client.config.config_helpers import get_connector_class
from hummingbot.client.settings import AllConnectorSettings
from hummingbot.connector.exchange.paper_trade.paper_trade_exchange import PaperTradeExchange
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker


def get_order_book_tracker(connector_name: str, trading_pairs: List[str]) -> OrderBookTracker:
    conn_setting = AllConnectorSettings.get_connector_settings()[connector_name]
    tracker_params = {"trading_pairs": trading_pairs}
    tracker_kwargs = conn_setting.add_domain_parameter(tracker_params)

    module_name = f"{conn_setting.base_name()}_order_book_tracker"
    class_name = "".join([o.capitalize() for o in module_name.split("_")])
    try:
        mod = importlib.import_module(f'hummingbot.connector.{conn_setting.type.name.lower()}.'
                                      f'{conn_setting.base_name()}.{module_name}')
        tracker_class = getattr(mod, class_name)
        return tracker_class(**tracker_kwargs)
    except ModuleNotFoundError:
        module_name = f"{conn_setting.base_name()}_api_order_book_data_source"
        class_name = f"{conn_setting.base_name().capitalize()}APIOrderBookDataSource"
        mod = importlib.import_module(f'hummingbot.connector.{conn_setting.type.name.lower()}.'
                                      f'{conn_setting.base_name()}.{module_name}')
        data_source_class = getattr(mod, class_name)
        data_source = data_source_class(**tracker_kwargs)
        return OrderBookTracker(data_source=data_source, **tracker_kwargs)
    except Exception as exception:
        raise Exception(f"Connector {connector_name} OrderBookTracker class not found ({exception})")


def create_paper_trade_market(exchange_name: str, trading_pairs: List[str]):
    tracker = get_order_book_tracker(connector_name=exchange_name, trading_pairs=trading_pairs)
    return PaperTradeExchange(tracker,
                              get_connector_class(exchange_name),
                              exchange_name=exchange_name)
