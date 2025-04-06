import os
from typing import IO, Callable, Optional, Union

from coinbase.constants import API_ENV_KEY, API_SECRET_ENV_KEY, WS_USER_BASE_URL

from .types.websocket_response import WebsocketResponse
from .websocket_base import WSBase, WSClientConnectionClosedException, WSClientException


class WSClient(WSBase):
    """
    **WSClient**
    _____________________________

    Initialize using WSClient

    __________

    **Parameters**:

    - **api_key | Optional (str)** - The API key
    - **api_secret | Optional (str)** - The API key secret
    - **key_file | Optional (IO | str)** - Path to API key file or file-like object
    - **base_url | (str)** - The websocket base url. Default set to "wss://advanced-trade-ws.coinbase.com"
    - **timeout | Optional (int)** - Set timeout in seconds for REST requests
    - **max_size | Optional (int)** - Max size in bytes for messages received. Default set to (10 * 1024 * 1024)
    - **on_message | Optional (Callable[[str], None])** - Function called when a message is received
    - **on_open | Optional ([Callable[[], None]])** - Function called when a connection is opened
    - **on_close | Optional ([Callable[[], None]])** - Function called when a connection is closed
    - **retry | Optional (bool)** - Enables automatic reconnections. Default set to True
    - **verbose | Optional (bool)** - Enables debug logging. Default set to False


    """

    from .channels import (
        candles,
        candles_async,
        candles_unsubscribe,
        candles_unsubscribe_async,
        futures_balance_summary,
        futures_balance_summary_async,
        futures_balance_summary_unsubscribe,
        futures_balance_summary_unsubscribe_async,
        heartbeats,
        heartbeats_async,
        heartbeats_unsubscribe,
        heartbeats_unsubscribe_async,
        level2,
        level2_async,
        level2_unsubscribe,
        level2_unsubscribe_async,
        market_trades,
        market_trades_async,
        market_trades_unsubscribe,
        market_trades_unsubscribe_async,
        status,
        status_async,
        status_unsubscribe,
        status_unsubscribe_async,
        ticker,
        ticker_async,
        ticker_batch,
        ticker_batch_async,
        ticker_batch_unsubscribe,
        ticker_batch_unsubscribe_async,
        ticker_unsubscribe,
        ticker_unsubscribe_async,
        user,
        user_async,
        user_unsubscribe,
        user_unsubscribe_async,
    )


class WSUserClient(WSBase):
    """
    **WSUserClient**
    _____________________________

    Initialize using WSUserClient

    __________

    **Parameters**:

    - **api_key | Optional (str)** - The API key
    - **api_secret | Optional (str)** - The API key secret
    - **key_file | Optional (IO | str)** - Path to API key file or file-like object
    - **base_url | (str)** - The websocket base url. Default set to "wss://advanced-trade-ws.coinbase.com"
    - **timeout | Optional (int)** - Set timeout in seconds for REST requests
    - **max_size | Optional (int)** - Max size in bytes for messages received. Default set to (10 * 1024 * 1024)
    - **on_message | Optional (Callable[[str], None])** - Function called when a message is received
    - **on_open | Optional ([Callable[[], None]])** - Function called when a connection is opened
    - **on_close | Optional ([Callable[[], None]])** - Function called when a connection is closed
    - **retry | Optional (bool)** - Enables automatic reconnections. Default set to True
    - **verbose | Optional (bool)** - Enables debug logging. Default set to False


    """

    from .channels import (
        futures_balance_summary,
        futures_balance_summary_async,
        futures_balance_summary_unsubscribe,
        futures_balance_summary_unsubscribe_async,
        heartbeats,
        heartbeats_async,
        heartbeats_unsubscribe,
        heartbeats_unsubscribe_async,
        user,
        user_async,
        user_unsubscribe,
        user_unsubscribe_async,
    )

    def __init__(
        self,
        api_key: Optional[str] = os.getenv(API_ENV_KEY),
        api_secret: Optional[str] = os.getenv(API_SECRET_ENV_KEY),
        key_file: Optional[Union[IO, str]] = None,
        base_url=WS_USER_BASE_URL,
        timeout: Optional[int] = None,
        max_size: Optional[int] = 10 * 1024 * 1024,
        on_message: Optional[Callable[[str], None]] = None,
        on_open: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        retry: Optional[bool] = True,
        verbose: Optional[bool] = False,
    ):
        super().__init__(
            api_key=api_key,
            api_secret=api_secret,
            key_file=key_file,
            base_url=base_url,
            timeout=timeout,
            max_size=max_size,
            on_message=on_message,
            on_open=on_open,
            on_close=on_close,
            retry=retry,
            verbose=verbose,
        )
