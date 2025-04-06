from typing import List

from coinbase.constants import (
    CANDLES,
    FUTURES_BALANCE_SUMMARY,
    HEARTBEATS,
    LEVEL2,
    MARKET_TRADES,
    STATUS,
    TICKER,
    TICKER_BATCH,
    USER,
)


def heartbeats(self) -> None:
    """
    **Heartbeats Subscribe**
    ________________________

    __________

    **Description:**

    Subscribe to heartbeats channel.

    __________

    **Read more on the official documentation:** `Heartbeats Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#heartbeats-channel>`_
    """
    self.subscribe([], [HEARTBEATS])


async def heartbeats_async(self) -> None:
    """
    **Heartbeats Subscribe Async**
    ______________________________

    __________

    **Description:**

    Async subscribe to heartbeats channel.

    __________

    **Read more on the official documentation:** `Heartbeats Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#heartbeats-channel>`_
    """
    await self.subscribe_async([], [HEARTBEATS])


def heartbeats_unsubscribe(self) -> None:
    """
    **Heartbeats Unsubscribe**
    __________________________

    __________

    **Description:**

    Unsubscribe to heartbeats channel.

    __________

    **Read more on the official documentation:** `Heartbeats Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#heartbeats-channel>`_
    """
    self.unsubscribe([], [HEARTBEATS])


async def heartbeats_unsubscribe_async(
    self,
) -> None:
    """
    **Heartbeats Unsubscribe Async**
    ________________________________

    __________

    **Description:**

    Async unsubscribe to heartbeats channel.

    __________

    **Read more on the official documentation:** `Heartbeats Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#heartbeats-channel>`_
    """
    await self.unsubscribe_async([], [HEARTBEATS])


def candles(self, product_ids: List[str]) -> None:
    """
    **Candles Subscribe**
    _____________________

    __________

    **Description:**

    Subscribe to candles channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Candles Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#candles-channel>`_
    """
    self.subscribe(product_ids, [CANDLES])


async def candles_async(self, product_ids: List[str]) -> None:
    """
    **Candles Subscribe Async**
    ___________________________

    __________

    **Description:**

    Async subscribe to candles channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Candles Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#candles-channel>`_
    """
    await self.subscribe_async(product_ids, [CANDLES])


def candles_unsubscribe(self, product_ids: List[str]) -> None:
    """
    **Candles Unsubscribe**
    _______________________

    __________

    **Description:**

    Unsubscribe to candles channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Candles Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#candles-channel>`_
    """
    self.unsubscribe(product_ids, [CANDLES])


async def candles_unsubscribe_async(self, product_ids: List[str]) -> None:
    """
    **Candles Unsubscribe Async**
    _____________________________

    __________

    **Description:**

    Async unsubscribe to candles channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Candles Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#candles-channel>`_
    """
    await self.unsubscribe_async(product_ids, [CANDLES])


def market_trades(self, product_ids: List[str]) -> None:
    """
    **Market Trades Subscribe**
    ___________________________

    __________

    **Description:**

    Subscribe to market_trades channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Market Trades Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#market-trades-channel>`_
    """
    self.subscribe(product_ids, [MARKET_TRADES])


async def market_trades_async(self, product_ids: List[str]) -> None:
    """
    **Market Trades Subscribe Async**
    _________________________________

    __________

    **Description:**

    Async subscribe to market_trades channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Market Trades Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#market-trades-channel>`_
    """
    await self.subscribe_async(product_ids, [MARKET_TRADES])


def market_trades_unsubscribe(self, product_ids: List[str]) -> None:
    """
    **Market Trades Unsubscribe**
    _____________________________

    __________

    **Description:**

    Unsubscribe to market_trades channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Market Trades Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#market-trades-channel>`_
    """
    self.unsubscribe(product_ids, [MARKET_TRADES])


async def market_trades_unsubscribe_async(self, product_ids: List[str]) -> None:
    """
    **Market Trades Unsubscribe Async**
    ___________________________________

    __________

    **Description:**

    Async unsubscribe to market_trades channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Market Trades Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#market-trades-channel>`_
    """
    await self.unsubscribe_async(product_ids, [MARKET_TRADES])


def status(self, product_ids: List[str]) -> None:
    """
    **Status Subscribe**
    ____________________

    __________

    **Description:**

    Subscribe to status channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Status Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#status-channel>`_
    """
    self.subscribe(product_ids, [STATUS])


async def status_async(self, product_ids: List[str]) -> None:
    """
    **Status Subscribe Async**
    __________________________

    __________

    **Description:**

    Async subscribe to status channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Status Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#status-channel>`_
    """
    await self.subscribe_async(product_ids, [STATUS])


def status_unsubscribe(self, product_ids: List[str]) -> None:
    """
    **Status Unsubscribe**
    ______________________

    __________

    **Description:**

    Unsubscribe to status channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Status Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#status-channel>`_
    """
    self.unsubscribe(product_ids, [STATUS])


async def status_unsubscribe_async(self, product_ids: List[str]) -> None:
    """
    **Status Unsubscribe Async**
    ____________________________

    __________

    **Description:**

    Async unsubscribe to status channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Status Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#status-channel>`_
    """
    await self.unsubscribe_async(product_ids, [STATUS])


def ticker(self, product_ids: List[str]) -> None:
    """
    **Ticker Subscribe**
    ____________________

    __________

    **Description:**

    Subscribe to ticker channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Ticker Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#ticker-channel>`_
    """
    self.subscribe(product_ids, [TICKER])


async def ticker_async(self, product_ids: List[str]) -> None:
    """
    **Ticker Subscribe Async**
    __________________________

    __________

    **Description:**

    Async subscribe to ticker channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Ticker Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#ticker-channel>`_
    """
    await self.subscribe_async(product_ids, [TICKER])


def ticker_unsubscribe(self, product_ids: List[str]) -> None:
    """
    **Ticker Unsubscribe**
    ______________________

    __________

    **Description:**

    Unsubscribe to ticker channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Ticker Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#ticker-channel>`_
    """
    self.unsubscribe(product_ids, [TICKER])


async def ticker_unsubscribe_async(self, product_ids: List[str]) -> None:
    """
    **Ticker Unsubscribe Async**
    ____________________________

    __________

    **Description:**

    Async unsubscribe to ticker channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Ticker Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#ticker-channel>`_
    """
    await self.unsubscribe_async(product_ids, [TICKER])


def ticker_batch(self, product_ids: List[str]) -> None:
    """
    **Ticker Batch Subscribe**
    __________________________

    __________

    **Description:**

    Subscribe to ticker_batch channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Ticker Batch Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#ticker-batch-channel>`_
    """
    self.subscribe(product_ids, [TICKER_BATCH])


async def ticker_batch_async(self, product_ids: List[str]) -> None:
    """
    **Ticker Batch Subscribe Async**
    ________________________________

    __________

    **Description:**

    Async subscribe to ticker_batch channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Ticker Batch Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#ticker-batch-channel>`_
    """
    await self.subscribe_async(product_ids, [TICKER_BATCH])


def ticker_batch_unsubscribe(self, product_ids: List[str]) -> None:
    """
    **Ticker Batch Unsubscribe**
    ____________________________

    __________

    **Description:**

    Unsubscribe to ticker_batch channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Ticker Batch Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#ticker-batch-channel>`_
    """
    self.unsubscribe(product_ids, [TICKER_BATCH])


async def ticker_batch_unsubscribe_async(self, product_ids: List[str]) -> None:
    """
    **Ticker Batch Unsubscribe Async**
    __________________________________

    __________

    **Description:**

    Async unsubscribe to ticker_batch channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Ticker Batch Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#ticker-batch-channel>`_
    """
    await self.unsubscribe_async(product_ids, [TICKER_BATCH])


def level2(self, product_ids: List[str]) -> None:
    """
    **Level2 Subscribe**
    ____________________

    __________

    **Description:**

    Subscribe to level2 channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Level2 Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#level2-channel>`_
    """
    self.subscribe(product_ids, [LEVEL2])


async def level2_async(self, product_ids: List[str]) -> None:
    """
    **Level2 Subscribe Async**
    __________________________

    __________

    **Description:**

    Async subscribe to level2 channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Level2 Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#level2-channel>`_
    """
    await self.subscribe_async(product_ids, [LEVEL2])


def level2_unsubscribe(self, product_ids: List[str]) -> None:
    """
    **Level2 Unsubscribe**
    ______________________

    __________

    **Description:**

    Unsubscribe to level2 channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Level2 Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#level2-channel>`_
    """
    self.unsubscribe(product_ids, [LEVEL2])


async def level2_unsubscribe_async(self, product_ids: List[str]) -> None:
    """
    **Level2 Unsubscribe Async**
    ____________________________

    __________

    **Description:**

    Async unsubscribe to level2 channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `Level2 Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#level2-channel>`_
    """
    await self.unsubscribe_async(product_ids, [LEVEL2])


def user(self, product_ids: List[str]) -> None:
    """
    **User Subscribe**
    __________________

    __________

    **Description:**

    Subscribe to user channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `User Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#user-channel>`_
    """
    self.subscribe(product_ids, [USER])


async def user_async(self, product_ids: List[str]) -> None:
    """
    **User Subscribe Async**
    ________________________

    __________

    **Description:**

    Async subscribe to user channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `User Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#user-channel>`_
    """
    await self.subscribe_async(product_ids, [USER])


def user_unsubscribe(self, product_ids: List[str]) -> None:
    """
    **User Unsubscribe**
    ____________________

    __________

    **Description:**

    Unsubscribe to user channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `User Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#user-channel>`_
    """
    self.unsubscribe(product_ids, [USER])


async def user_unsubscribe_async(self, product_ids: List[str]) -> None:
    """
    **User Unsubscribe Async**
    __________________________

    __________

    **Description:**

    Async unsubscribe to user channel for a list of products_ids.

    __________

    **Read more on the official documentation:** `User Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#user-channel>`_
    """
    await self.unsubscribe_async(product_ids, [USER])


def futures_balance_summary(self) -> None:
    """
    **Futures Balance Summary Subscribe**
    __________________

    __________

    **Description:**

    Subscribe to futures_balance_summary channel.

    __________

    **Read more on the official documentation:** `Futures Balance Summary Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#futures-balance-summary-channel>`_
    """
    self.subscribe([], [FUTURES_BALANCE_SUMMARY])


async def futures_balance_summary_async(self) -> None:
    """
    **Futures Balance Summary Subscribe Async**
    ________________________

    __________

    **Description:**

    Async subscribe to futures_balance_summary channel.

    __________

    **Read more on the official documentation:** `Futures Balance Summary Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#futures-balance-summary-channel>`_
    """
    await self.subscribe_async([], [FUTURES_BALANCE_SUMMARY])


def futures_balance_summary_unsubscribe(self) -> None:
    """
    **Futures Balance Summary Unsubscribe**
    ____________________

    __________

    **Description:**

    Unsubscribe to futures_balance_summary channel.

    __________

    **Read more on the official documentation:** `Futures Balance Summary Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#futures-balance-summary-channel>`_
    """
    self.unsubscribe([], [FUTURES_BALANCE_SUMMARY])


async def futures_balance_summary_unsubscribe_async(self) -> None:
    """
    **Futures Balance Summary Unsubscribe Async**
    __________________________

    __________

    **Description:**

    Async unsubscribe to futures_balance_summary channel.

    __________

    **Read more on the official documentation:** `Futures Balance Summary Channel
    <https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#futures-balance-summary-channel>`_
    """
    await self.unsubscribe_async([], [FUTURES_BALANCE_SUMMARY])
