# hummingbot/connector/exchange/zaif/zaif_web_utils.py

from typing import Optional

from hummingbot.connector.exchange.zaif import zaif_constants as CONSTANTS
from hummingbot.connector.exchange.zaif.zaif_auth import ZaifAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str) -> str:
    return f"{CONSTANTS.PUBLIC_API_BASE_URL}{path_url}"

def private_rest_url() -> str:
    return CONSTANTS.PRIVATE_API_BASE_URL

def build_api_factory(
    throttler: AsyncThrottler,
    auth: ZaifAuth,
) -> WebAssistantsFactory:
    """
    Zaif API とやり取りするための WebAssistantsFactory を構築します。

    :param throttler: レートリミット制御のための AsyncThrottler インスタンス
    :param auth: 認証付きリクエストのための ZaifAuth インスタンス
    :return: 構築された WebAssistantsFactory インスタンス
    """
    throttler = throttler or AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
    )
    return api_factory

def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


import aiohttp


async def get_current_server_time() -> float:
    url = public_rest_url(CONSTANTS.SERVER_TIME_PATH_URL)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            return float(data["timestamp"])

