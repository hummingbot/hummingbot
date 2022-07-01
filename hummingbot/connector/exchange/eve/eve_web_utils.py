from urllib.parse import urljoin

from hummingbot.connector.exchange.alpha_point.alpha_point_web_utils import AlphaPointURLCreatorBase
from hummingbot.connector.exchange.eve import eve_constants as CONSTANTS


class EveURLCreator(AlphaPointURLCreatorBase):
    def __init__(self, rest_base_url: str, ws_base_url: str):
        self._rest_base_url = rest_base_url
        self._ws_base_url = ws_base_url

    def get_rest_url(self, path_url: str) -> str:
        base_url = f"{self._rest_base_url}/{CONSTANTS.VERSION_PATH}"
        return urljoin(base_url, path_url)

    def get_ws_url(self) -> str:
        return self._ws_base_url
