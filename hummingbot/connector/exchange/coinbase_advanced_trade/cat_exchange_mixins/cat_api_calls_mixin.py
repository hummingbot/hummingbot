from asyncio import Protocol
from typing import Any, Dict


class _APICallsMixinProtocol(Protocol):
    async def _api_post(self, *args, **kwargs) -> Dict[str, Any]:
        ...

    async def _api_delete(self, *args, **kwargs) -> Dict[str, Any]:
        ...

    async def _api_get(self, *args, **kwargs) -> Dict[str, Any]:
        ...


class CoinbaseAdvancedTradeAPICallsMixin:
    def __init__(self, **kwargs):
        if super().__class__ is not object:
            super().__init__(**kwargs)

    # @cat_api_call_http_error_handler
    async def api_post(self: _APICallsMixinProtocol, *args, **kwargs) -> Dict[str, Any]:
        kwargs["return_err"] = True
        return await self._api_post(*args, **kwargs)

    # @cat_api_call_http_error_handler
    async def api_delete(self: _APICallsMixinProtocol, *args, **kwargs) -> Dict[str, Any]:
        kwargs["return_err"] = True
        return await self._api_delete(*args, **kwargs)

    # @cat_api_call_http_error_handler
    async def api_get(self: _APICallsMixinProtocol, *args, **kwargs) -> Dict[str, Any]:
        kwargs["return_err"] = True
        return await self._api_get(*args, **kwargs)
