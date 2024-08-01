from typing import Any, Dict, List, Optional

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.gateway_clob_api_data_source_base import (
    GatewayCLOBAPIDataSourceBase,
)
from hummingbot.connector.gateway.clob_spot.data_sources.rubicon.rubicon_constants import CONNECTOR_NAME
from hummingbot.core.data_type.common import OrderType
from hummingbot.logger import HummingbotLogger


class RubiconAPIDataSource(GatewayCLOBAPIDataSourceBase):
    _logger: Optional[HummingbotLogger] = None

    def __init__(
            self,
            trading_pairs: List[str],
            connector_spec: Dict[str, Any],
            client_config_map: ClientConfigAdapter,
    ):
        super().__init__(
            trading_pairs=trading_pairs,
            connector_spec=connector_spec,
            client_config_map=client_config_map
        )

    @property
    def connector_name(self) -> str:
        return CONNECTOR_NAME

    @property
    def events_are_streamed(self) -> bool:
        return False

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET]
