from typing import TYPE_CHECKING, List, Optional

from hummingbot.connector.exchange.penumbra.penumbra_constants import EXCHANGE_NAME
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.web_assistant.auth import AuthBase

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class PenumbraExchange(ExchangePyBase):

    def __init__(
            self,
            client_config_map: "ClientConfigAdapter",
            trading_pairs: Optional[List[str]] = None,
            trading_required: bool = True,
    ):
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs

        super().__init__(client_config_map=client_config_map)

    @property
    def name(self) -> str:
        return EXCHANGE_NAME

    @property
    def authenticator(self) -> AuthBase:
        return None

    @property
    def client_order_id_max_length(self) -> int:
        return None

    @property
    def client_order_id_prefix(self) -> str:
        return ""

    @property
    def trading_rules_request_path(self) -> str:
        raise NotImplementedError

    @property
    def trading_pairs_request_path(self) -> str:
        raise NotImplementedError

    @property
    def check_network_request_path(self) -> str:
        raise NotImplementedError

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return False

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required
