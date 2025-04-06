import asyncio
import json
import logging
import os
import ssl
import threading
import time
from multiprocessing import AuthenticationError
from typing import IO, Callable, List, Optional, Union

import backoff
import websockets

from coinbase import jwt_generator
from coinbase.api_base import APIBase, get_logger
from coinbase.constants import (
    API_ENV_KEY,
    API_SECRET_ENV_KEY,
    SUBSCRIBE_MESSAGE_TYPE,
    UNSUBSCRIBE_MESSAGE_TYPE,
    USER_AGENT,
    WS_AUTH_CHANNELS,
    WS_BASE_URL,
    WS_RETRY_BASE,
    WS_RETRY_FACTOR,
    WS_RETRY_MAX,
)

logger = get_logger("coinbase.WSClient")


class WSClientException(Exception):
    """
    **WSClientException**
    ________________________________________

    -----------------------------------------

    Exception raised for errors in the WebSocket client.
    """

    pass


class WSClientConnectionClosedException(Exception):
    """
    **WSClientConnectionClosedException**
    ________________________________________

    ----------------------------------------

    Exception raised for unexpected closure in the WebSocket client.
    """

    pass


class WSBase(APIBase):
    """
    :meta private:
    """

    def __init__(
        self,
        api_key: Optional[str] = os.getenv(API_ENV_KEY),
        api_secret: Optional[str] = os.getenv(API_SECRET_ENV_KEY),
        key_file: Optional[Union[IO, str]] = None,
        base_url=WS_BASE_URL,
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
            verbose=verbose,
        )

        if not on_message:
            raise WSClientException("on_message callback is required.")

        if verbose:
            logger.setLevel(logging.DEBUG)

        self.max_size = max_size
        self.on_message = on_message
        self.on_open = on_open
        self.on_close = on_close

        self.websocket = None
        self.loop = None
        self.thread = None
        self._task = None

        self.retry = retry
        self._retry_max_tries = WS_RETRY_MAX
        self._retry_base = WS_RETRY_BASE
        self._retry_factor = WS_RETRY_FACTOR
        self._retry_count = 0

        self.subscriptions = {}
        self._background_exception = None
        self._retrying = False

    def open(self) -> None:
        """
        **Open Websocket**
        __________________

        ------------------------

        Open the websocket client connection.
        """
        if not self.loop or self.loop.is_closed():
            self.loop = asyncio.new_event_loop()  # Create a new event loop
            self.thread = threading.Thread(target=self.loop.run_forever)
            self.thread.daemon = True
            self.thread.start()

        self._run_coroutine_threadsafe(self.open_async())

    async def open_async(self) -> None:
        """
        **Open Websocket Async**
        ________________________

        ------------------------

        Open the websocket client connection asynchronously.
        """
        self._ensure_websocket_not_open()

        headers = self._set_headers()

        logger.debug("Connecting to %s", self.base_url)
        try:
            self.websocket = await websockets.connect(
                self.base_url,
                open_timeout=self.timeout,
                max_size=self.max_size,
                user_agent_header=USER_AGENT,
                extra_headers=headers,
                ssl=ssl.SSLContext() if self.base_url.startswith("wss://") else None,
            )
            logger.debug("Successfully connected to %s", self.base_url)

            if self.on_open:
                self.on_open()

            # Start the message handler coroutine after establishing connection
            if not self._retrying:
                self._task = asyncio.create_task(self._message_handler())

        except asyncio.TimeoutError as toe:
            self.websocket = None
            logger.error("Connection attempt timed out: %s", toe)
            raise WSClientException("Connection attempt timed out") from toe
        except (websockets.exceptions.WebSocketException, OSError) as wse:
            self.websocket = None
            logger.error("Failed to establish WebSocket connection: %s", wse)
            raise WSClientException("Failed to establish WebSocket connection") from wse

    def close(self) -> None:
        """
        **Close Websocket**
        ___________________

        ------------------------

        Close the websocket client connection.
        """
        if self.loop and not self.loop.is_closed():
            # Schedule the asynchronous close
            self._run_coroutine_threadsafe(self.close_async())
            # Stop the event loop
            self.loop.call_soon_threadsafe(self.loop.stop)
            # Wait for the thread to finish
            self.thread.join()
            # Close the event loop
            self.loop.close()
        else:
            raise WSClientException("Event loop is not running.")

    async def close_async(self) -> None:
        """
        **Close Websocket Async**
        _________________________

        ------------------------

        Close the websocket client connection asynchronously.
        """
        self._ensure_websocket_open()

        logger.debug("Closing connection to %s", self.base_url)
        try:
            await self.websocket.close()
            self.websocket = None
            self.subscriptions = {}

            logger.debug("Connection closed to %s", self.base_url)

            if self.on_close:
                self.on_close()
        except (websockets.exceptions.WebSocketException, OSError) as wse:
            logger.error("Failed to close WebSocket connection: %s", wse)
            raise WSClientException("Failed to close WebSocket connection.") from wse

    def subscribe(self, product_ids: List[str], channels: List[str]) -> None:
        """
        **Subscribe**
        _____________

        ------------------------

        Subscribe to a list of channels for a list of product ids.

        - **product_ids** - product ids to subscribe to
        - **channels** - channels to subscribe to
        """
        if self.loop and not self.loop.is_closed():
            self._run_coroutine_threadsafe(self.subscribe_async(product_ids, channels))
        else:
            raise WSClientException("Websocket Client is not open.")

    async def subscribe_async(
        self, product_ids: List[str], channels: List[str]
    ) -> None:
        """
        **Subscribe Async**
        ___________________

        ------------------------

        Async subscribe to a list of channels for a list of product ids.

        - **product_ids** - product ids to subscribe to
        - **channels** - channels to subscribe to
        """
        self._ensure_websocket_open()
        for channel in channels:
            try:
                if not self.is_authenticated and channel in WS_AUTH_CHANNELS:
                    raise AuthenticationError(
                        "Unauthenticated request to private channel."
                    )

                is_public = False if channel in WS_AUTH_CHANNELS else True
                message = self._build_subscription_message(
                    product_ids, channel, SUBSCRIBE_MESSAGE_TYPE, is_public
                )
                json_message = json.dumps(message)

                logger.debug(
                    "Subscribing to channel %s for product IDs: %s",
                    channel,
                    product_ids,
                )

                await self.websocket.send(json_message)

                logger.debug("Successfully sent subscription message.")

                # add to subscriptions map
                if channel not in self.subscriptions:
                    self.subscriptions[channel] = set()
                self.subscriptions[channel].update(product_ids)
            except websockets.exceptions.WebSocketException as wse:
                logger.error(
                    "Failed to subscribe to %s channel for product IDs %s: %s",
                    channel,
                    product_ids,
                    wse,
                )
                raise WSClientException(
                    f"Failed to subscribe to {channel} channel for product ids {product_ids}."
                ) from wse

    def unsubscribe(self, product_ids: List[str], channels: List[str]) -> None:
        """
        **Unsubscribe**
        _______________

        ------------------------

        Unsubscribe to a list of channels for a list of product ids.

        - **product_ids** - product ids to unsubscribe from
        - **channels** - channels to unsubscribe from
        """
        if self.loop and not self.loop.is_closed():
            self._run_coroutine_threadsafe(
                self.unsubscribe_async(product_ids, channels)
            )
        else:
            raise WSClientException("Websocket Client is not open.")

    async def unsubscribe_async(
        self, product_ids: List[str], channels: List[str]
    ) -> None:
        """
        **Unsubscribe Async**
        _____________________

        ------------------------

        Async unsubscribe to a list of channels for a list of product ids.

        - **product_ids** - product ids to unsubscribe from
        - **channels** - channels to unsubscribe from
        """
        self._ensure_websocket_open()
        for channel in channels:
            try:
                if not self.is_authenticated and channel in WS_AUTH_CHANNELS:
                    raise AuthenticationError(
                        "Unauthenticated request to private channel. If you wish to access private channels, you must provide your API key and secret when initializing the WSClient."
                    )
                is_public = False if channel in WS_AUTH_CHANNELS else True
                message = self._build_subscription_message(
                    product_ids, channel, UNSUBSCRIBE_MESSAGE_TYPE, is_public
                )
                json_message = json.dumps(message)

                logger.debug(
                    "Unsubscribing from channel %s for product IDs: %s",
                    channel,
                    product_ids,
                )

                await self.websocket.send(json_message)

                logger.debug("Successfully sent unsubscribe message.")

                # remove from subscriptions map
                if channel in self.subscriptions:
                    self.subscriptions[channel].difference_update(product_ids)
            except (websockets.exceptions.WebSocketException, OSError) as wse:
                logger.error(
                    "Failed to unsubscribe to %s channel for product IDs %s: %s",
                    channel,
                    product_ids,
                    wse,
                )

                raise WSClientException(
                    f"Failed to unsubscribe to {channel} channel for product ids {product_ids}."
                ) from wse

    def unsubscribe_all(self) -> None:
        """
        **Unsubscribe All**
        ________________________

        ------------------------

        Unsubscribe from all channels you are currently subscribed to.
        """
        if self.loop and not self.loop.is_closed():
            self._run_coroutine_threadsafe(self.unsubscribe_all_async())
        else:
            raise WSClientException("Websocket Client is not open.")

    async def unsubscribe_all_async(self) -> None:
        """
        **Unsubscribe All Async**
        _________________________

        ------------------------

        Async unsubscribe from all channels you are currently subscribed to.
        """
        for channel, product_ids in self.subscriptions.items():
            if product_ids:
                await self.unsubscribe_async(list(product_ids), [channel])

    def sleep_with_exception_check(self, sleep: int) -> None:
        """
        **Sleep with Exception Check**
        ______________________________

        ------------------------

        Sleep for a specified number of seconds and check for background exceptions.

        - **sleep** - number of seconds to sleep.
        """
        time.sleep(sleep)
        self.raise_background_exception()

    async def sleep_with_exception_check_async(self, sleep: int) -> None:
        """
        **Sleep with Exception Check Async**
        ____________________________________

        ------------------------

        Async sleep for a specified number of seconds and check for background exceptions.

        - **sleep** - number of seconds to sleep.
        """
        await asyncio.sleep(sleep)
        self.raise_background_exception()

    def run_forever_with_exception_check(self) -> None:
        """
        **Run Forever with Exception Check**
        ____________________________________

        ------------------------

        Runs an endless loop, checking for background exceptions every second.
        """
        while True:
            time.sleep(1)
            self.raise_background_exception()

    async def run_forever_with_exception_check_async(self) -> None:
        """
        **Run Forever with Exception Check Async**
        __________________________________________

        ------------------------

        Async runs an endless loop, checking for background exceptions every second.
        """
        while True:
            await asyncio.sleep(1)
            self.raise_background_exception()

    def raise_background_exception(self) -> None:
        """
        **Raise Background Exception**
        ______________________________

        ------------------------

        Raise any background exceptions that occurred in the message handler.
        """
        if self._background_exception:
            exception_to_raise = self._background_exception
            self._background_exception = None
            raise exception_to_raise

    def _run_coroutine_threadsafe(self, coro):
        """
        :meta private:
        """
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def _is_websocket_open(self):
        """
        :meta private:
        """
        return self.websocket and self.websocket.open

    async def _resubscribe(self):
        """
        :meta private:
        """
        for channel, product_ids in self.subscriptions.items():
            if product_ids:
                await self.subscribe_async(list(product_ids), [channel])

    async def _retry_connection(self):
        """
        :meta private:
        """
        self._retry_count = 0

        @backoff.on_exception(
            backoff.expo,
            WSClientException,
            max_tries=self._retry_max_tries,
            base=self._retry_base,
            factor=self._retry_factor,
        )
        async def _retry_connect_and_resubscribe():
            self._retry_count += 1

            logger.debug("Retrying connection attempt %s", self._retry_count)
            if not self._is_websocket_open():
                await self.open_async()

            logger.debug("Resubscribing to channels")
            self._retry_count = 0
            await self._resubscribe()

        return await _retry_connect_and_resubscribe()

    async def _message_handler(self):
        """
        :meta private:
        """
        self.handler_open = True
        while self._is_websocket_open():
            try:
                message = await self.websocket.recv()
                if self.on_message:
                    self.on_message(message)
            except websockets.exceptions.ConnectionClosedOK as cco:
                logger.debug("Connection closed (OK): %s", cco)
                break
            except websockets.exceptions.ConnectionClosedError as cce:
                logger.error("Connection closed (ERROR): %s", cce)
                if self.retry:
                    self._retrying = True
                    try:
                        logger.debug("Retrying connection")
                        await self._retry_connection()
                        self._retrying = False
                    except WSClientException:
                        logger.error(
                            "Connection closed unexpectedly. Retry attempts failed."
                        )
                        self._background_exception = WSClientConnectionClosedException(
                            "Connection closed unexpectedly. Retry attempts failed."
                        )
                        self.subscriptions = {}
                        self._retrying = False
                        self._retry_count = 0
                        break
                else:
                    logger.error("Connection closed unexpectedly with error: %s", cce)
                    self._background_exception = WSClientConnectionClosedException(
                        f"Connection closed unexpectedly with error: {cce}"
                    )
                    self.subscriptions = {}
                    break
            except (
                websockets.exceptions.WebSocketException,
                json.JSONDecodeError,
                WSClientException,
            ) as e:
                logger.error("Exception in message handler: %s", e)
                self._background_exception = WSClientException(
                    f"Exception in message handler: {e}"
                )
                break

    def _build_subscription_message(
        self, product_ids: List[str], channel: str, message_type: str, public: bool
    ):
        """
        :meta private:
        """
        return {
            "type": message_type,
            "product_ids": product_ids,
            "channel": channel,
            **(
                {
                    "jwt": jwt_generator.build_ws_jwt(self.api_key, self.api_secret),
                }
                if self.is_authenticated
                else {}
            ),
        }

    def _ensure_websocket_not_open(self):
        """
        :meta private:
        """
        if self._is_websocket_open():
            raise WSClientException("WebSocket is already open.")

    def _ensure_websocket_open(self):
        """
        :meta private:
        """
        if not self._is_websocket_open():
            raise WSClientException("WebSocket is closed or was never opened.")

    def _set_headers(self):
        """
        :meta private:
        """
        if self._retry_count > 0:
            return {"x-cb-retry-counter": str(self._retry_count)}
        else:
            return {}
