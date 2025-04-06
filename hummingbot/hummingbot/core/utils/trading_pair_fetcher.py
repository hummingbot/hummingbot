import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.settings import AllConnectorSettings, ConnectorSetting
from hummingbot.logger import HummingbotLogger

from ...client.config.security import Security
from .async_utils import safe_ensure_future


class TradingPairFetcher:
    _sf_shared_instance: "TradingPairFetcher" = None
    _tpf_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._tpf_logger is None:
            cls._tpf_logger = logging.getLogger(__name__)
        return cls._tpf_logger

    @classmethod
    def get_instance(cls, client_config_map: Optional["ClientConfigAdapter"] = None) -> "TradingPairFetcher":
        if cls._sf_shared_instance is None:
            client_config_map = client_config_map or cls._get_client_config_map()
            cls._sf_shared_instance = TradingPairFetcher(client_config_map)
        return cls._sf_shared_instance

    def __init__(self, client_config_map: ClientConfigAdapter):
        self.ready = False
        self.trading_pairs: Dict[str, Any] = {}
        self.fetch_pairs_from_all_exchanges = client_config_map.fetch_pairs_from_all_exchanges
        self._fetch_task = safe_ensure_future(self.fetch_all(client_config_map))

    def _fetch_pairs_from_connector_setting(
            self,
            connector_setting: ConnectorSetting,
            connector_name: Optional[str] = None):
        connector_name = connector_name or connector_setting.name
        connector = connector_setting.non_trading_connector_instance_with_default_configuration()
        safe_ensure_future(self.call_fetch_pairs(connector.all_trading_pairs(), connector_name))

    async def fetch_all(self, client_config_map: ClientConfigAdapter):
        await Security.wait_til_decryption_done()
        connector_settings = self._all_connector_settings()
        for conn_setting in connector_settings.values():
            # XXX(martin_kou): Some connectors, e.g. uniswap v3, aren't completed yet. Ignore if you can't find the
            # data source module for them.
            try:
                if conn_setting.base_name().endswith("paper_trade"):
                    self._fetch_pairs_from_connector_setting(
                        connector_setting=connector_settings[conn_setting.parent_name],
                        connector_name=conn_setting.name
                    )
                elif not self.fetch_pairs_from_all_exchanges:
                    if conn_setting.connector_connected():
                        self._fetch_pairs_from_connector_setting(connector_setting=conn_setting)
                else:
                    self._fetch_pairs_from_connector_setting(connector_setting=conn_setting)
            except ModuleNotFoundError:
                continue
            except Exception:
                self.logger().exception(f"An error occurred when fetching trading pairs for {conn_setting.name}."
                                        "Please check the logs")
        self.ready = True

    async def call_fetch_pairs(self, fetch_fn: Callable[[], Awaitable[List[str]]], exchange_name: str):
        try:
            pairs = await fetch_fn
            self.trading_pairs[exchange_name] = pairs
        except Exception:
            self.logger().error(f"Connector {exchange_name} failed to retrieve its trading pairs. "
                                f"Trading pairs autocompletion won't work.", exc_info=True)
            # In case of error just assign empty list, this is st. the bot won't stop working
            self.trading_pairs[exchange_name] = []

    def _all_connector_settings(self) -> Dict[str, ConnectorSetting]:
        # Method created to enabling patching in unit tests
        return AllConnectorSettings.get_connector_settings()

    @staticmethod
    def _get_client_config_map() -> "ClientConfigAdapter":
        from hummingbot.client.hummingbot_application import HummingbotApplication

        client_config_map = HummingbotApplication.main_application().client_config_map
        return client_config_map
