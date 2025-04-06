#!/usr/bin/env python

from aiohttp import ClientRequest
import certifi
import ssl
from typing import Optional


class SSLClientRequest(ClientRequest):
    _sslcr_default_ssl_context: Optional[ssl.SSLContext] = None

    @classmethod
    def default_ssl_context(cls) -> ssl.SSLContext:
        if cls._sslcr_default_ssl_context is None:
            cls._sslcr_default_ssl_context = ssl.create_default_context(cafile=certifi.where())
        return cls._sslcr_default_ssl_context

    def __init__(self, *args, **kwargs):
        if "ssl" not in kwargs or kwargs["ssl"] is None:
            kwargs["ssl"] = self.default_ssl_context()
        super().__init__(*args, **kwargs)
