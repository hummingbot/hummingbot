from typing import Any, Dict

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_errors import (
    cat_api_call_http_error_handler,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_operational_errors import (
    cat_api_call_operational_error_handler,
)


class _APICallsMixinSuperCalls:
    @cat_api_call_http_error_handler
    @cat_api_call_operational_error_handler
    async def _api_post(self, *args, **kwargs) -> Dict[str, Any]:
        kwargs["return_err"] = True
        return await super()._api_post(*args, **kwargs)

    @cat_api_call_http_error_handler
    @cat_api_call_operational_error_handler
    async def _api_delete(self, *args, **kwargs) -> Dict[str, Any]:
        kwargs["return_err"] = True
        return await super()._api_delete(*args, **kwargs)

    @cat_api_call_http_error_handler
    @cat_api_call_operational_error_handler
    async def _api_get(self, *args, **kwargs) -> Dict[str, Any]:
        kwargs["return_err"] = True
        return await super()._api_get(*args, **kwargs)
