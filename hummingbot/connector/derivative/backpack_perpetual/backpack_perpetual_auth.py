"""
Backpack Perpetual Auth - Reuses the spot connector's authentication.

The authentication mechanism is identical for both spot and perpetual trading.
"""

from typing import Any, Dict, Optional

from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_constants as CONSTANTS
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class BackpackPerpetualAuth(BackpackAuth):
    """
    Auth class for Backpack Perpetual using ED25519 signatures.

    This class inherits from the spot connector's BackpackAuth since
    the authentication mechanism is identical for perpetual trading.
    """

    def _infer_instruction(
        self,
        method: RESTMethod,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        url_lower = url.lower()

        if CONSTANTS.POSITION_URL in url_lower or CONSTANTS.POSITIONS_URL in url_lower:
            return CONSTANTS.INSTRUCTION_POSITION_QUERY
        if CONSTANTS.LEVERAGE_URL in url_lower and method == RESTMethod.POST:
            return CONSTANTS.INSTRUCTION_LEVERAGE_UPDATE

        return super()._infer_instruction(method=method, url=url, params=params)
