from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.eve import eve_constants as CONSTANTS
from hummingbot.connector.exchange.eve.eve_web_utils import EveURLCreator
from hummingbot.connector.utilities.oms_connector.oms_connector_exchange import OMSExchange

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class EveExchange(OMSExchange):
    def __init__(
        self,
        client_config_map: "ClientConfigAdapter",
        eve_api_key: str,
        eve_secret_key: str,
        eve_user_id: int,
        trading_pairs: Optional[List[str]] = None,
        trading_required: bool = True,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        url_creator: Optional[EveURLCreator] = None,
    ):
        self._domain = domain
        url_creator = url_creator or EveURLCreator(
            rest_base_url=CONSTANTS.REST_URLS[self._domain],
            ws_base_url=CONSTANTS.WS_URLS[self._domain],
        )
        super().__init__(
            client_config_map=client_config_map,
            api_key=eve_api_key,
            secret_key=eve_secret_key,
            user_id=eve_user_id,
            trading_pairs=trading_pairs,
            trading_required=trading_required,
            url_creator=url_creator,
        )

    @property
    def name(self) -> str:
        return "eve"

    @property
    def oms_id(self) -> int:
        return CONSTANTS.OMS_ID

    @property
    def domain(self):
        return self._domain
