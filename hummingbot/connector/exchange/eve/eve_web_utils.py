from urllib.parse import urljoin

from hummingbot.connector.exchange.eve import eve_constants as CONSTANTS
from hummingbot.connector.utilities.oms_connector.oms_connector_web_utils import OMSConnectorURLCreatorBase


class EveURLCreator(OMSConnectorURLCreatorBase):
    def __init__(self, rest_base_url: str, ws_base_url: str):
        self._rest_base_url = rest_base_url
        self._ws_base_url = ws_base_url

    def get_rest_url(self, path_url: str) -> str:
        base_url = f"{self._rest_base_url}/{CONSTANTS.VERSION_PATH}/"
        return urljoin(base_url, path_url)

    def get_ws_url(self) -> str:
        return self._ws_base_url
