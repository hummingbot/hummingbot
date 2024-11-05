import logging
from typing import Dict, Optional

from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants import (
    WS_ORDER_SUBSCRIPTION_CHANNELS,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_web_utils import (
    get_timestamp_from_exchange_time,
)
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.logger import HummingbotLogger


class CoinbaseAdvancedTradeOrderBook(OrderBook):
    """
    Coinbase Advanced Trade Order Book class
    """
    # Mapping of WS channels to their respective sequence numbers
    _sequence_nums: Dict[str, int] = {channel: 0 for channel in WS_ORDER_SUBSCRIPTION_CHANNELS.inv.keys()}

    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | logging.Logger:
        if cls._logger is None:
            name: str = HummingbotLogger.logger_name_for_class(cls)
            cls._logger = logging.getLogger(name)
        return cls._logger

    @classmethod
    def snapshot_message_from_exchange(cls,
                                       msg: Dict[str, any],
                                       timestamp: float,
                                       metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Creates a snapshot message with the order book snapshot message
        :param msg: the response from the exchange when requesting the order book snapshot
        :param timestamp: the snapshot timestamp
        :param metadata: a dictionary with extra information to add to the snapshot data
        :return: a snapshot message with the snapshot information received from the exchange
        """
        if metadata:
            msg.update(metadata)
        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, {
            "trading_pair": msg["trading_pair"],
            "update_id": int(get_timestamp_from_exchange_time(msg["pricebook"]["time"], "s")),
            "bids": [[d["price"], d["size"]] for d in msg["pricebook"]["bids"]],
            "asks": [[d["price"], d["size"]] for d in msg["pricebook"]["asks"]]
        }, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(
            cls,
            msg: Dict[str, any],
            timestamp: Optional[float] = None,
            metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Process messages from the order book or trade channel
        https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#level2-channel
        The snapshot is the first message received form the 'level2' channel. It has a sequence_num = 0
        :param msg: the response from the exchange when requesting the order book snapshot
        :param symbol_to_pair: Method to retrieve a Hummingbot trading pair from an exchange symbol
        :return: a snapshot message with the snapshot information received from the exchange
        {
            'channel': 'l2_data',
            'client_id': '',
            'timestamp': '2024-10-08T09:10:36.04370306Z',
            'sequence_num': 9,
            'events': [
                {
                    'type': 'update',
                    'product_id': 'BTC-USD',
                    'updates': [
                        {
                            'side': 'bid',
                            'event_time': '2024-10-08T09:10:34.970831Z',
                            'price_level': '62319.46',
                            'new_quantity': '0.00169'
                        },
                        {
                            'side': 'bid',
                            'event_time': '2024-10-08T09:10:34.970831Z',
                            'price_level': '62318.81',
                            'new_quantity': '0'
                        },
                        {
                            'side': 'offer'
                            'event_time': '2024-10-08T09:10:34.970831Z',
                            'price_level': '62336.65',
                            'new_quantity': '0.03021537'
                        }
                    ]
                }
            ]
        }
        """
        if metadata:
            msg.update(metadata)
        event = msg["events"][0]
        # trading_pair = event["product_id"]
        obm_content = {
            "trading_pair": msg["trading_pair"],
            "update_id": int(get_timestamp_from_exchange_time(msg["timestamp"], "s")),
            "bids": [],
            "asks": []
        }
        for update in event.get("updates", []):
            if update["side"] == "bid":
                obm_content["bids"].append([update["price_level"], update["new_quantity"]])
            else:
                obm_content["asks"].append([update["price_level"], update["new_quantity"]])

        return OrderBookMessage(
            OrderBookMessageType.DIFF,
            obm_content,
            timestamp=obm_content['update_id'])

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Process messages from the market trades channel
        https://docs.cdp.coinbase.com/advanced-trade/docs/ws-channels#market-trades-channel
        :param msg: the response from the exchange when requesting the order book snapshot
        :param symbol_to_pair: Method to retrieve a Hummingbot trading pair from an exchange symbol
        :return: a trade message with the trade information received from the exchange
        {
            'channel': 'market_trades',
            'client_id': '',
            'timestamp': '2024-10-08T09:10:52.425044603Z',
            'sequence_num': 328,
            'events': [
                {
                    'type': 'update',
                    'trades': [
                        {
                            'product_id': 'BTC-USD',
                            'trade_id': '699871154',
                            'price': '62322.43',
                            'size': '0.00005535',
                            'time': '2024-10-08T09:10:52.378779Z',
                            'side': 'BUY'
                        }
                    ]
                }
            ]
        }
        """
        if metadata:
            msg.update(metadata)
        event = msg["events"][0]
        ts: float = get_timestamp_from_exchange_time(msg["timestamp"], "s")
        update = event["trades"][0]
        # Return an OrderBookMessage for each trade processed
        return OrderBookMessage(
            OrderBookMessageType.TRADE,
            {
                "trading_pair": msg["trading_pair"],
                "trade_type": float(TradeType.SELL.value) if update["side"] == "SELL" else float(TradeType.BUY.value),
                "trade_id": int(update["trade_id"]),
                "update_id": int(ts),
                "price": update["price"],
                "amount": update["size"]
            },
            timestamp=ts)
