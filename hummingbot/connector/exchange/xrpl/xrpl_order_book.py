from typing import Dict, Optional

from xrpl.utils import drops_to_xrp

from hummingbot.connector.exchange.xrpl.xrpl_utils import normalize_price_from_drop
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class XRPLOrderBook(OrderBook):

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
        is_xrp_pair = False

        if metadata:
            msg.update(metadata)
            trading_pair = metadata["trading_pair"]
            # split trading pair to get token, then check if token is XRP
            is_xrp_pair = trading_pair.split("-")[1] == "XRP" or trading_pair.split("-")[0] == "XRP"

        raw_asks = msg["asks"]
        raw_bids = msg["bids"]
        processed_asks = []
        processed_bids = []

        for ask in raw_asks:
            price = float(normalize_price_from_drop(ask["quality"], is_ask=True)) if is_xrp_pair else float(
                ask["quality"])

            # Check if taker_gets is string or object
            if isinstance(ask["TakerGets"], str):
                quantity = float(drops_to_xrp(ask["TakerGets"])) if is_xrp_pair else float(ask["TakerGets"])
            else:
                quantity = float(ask["TakerGets"]["value"])

            update_id = int(ask["Sequence"])

            processed_asks.append(OrderBookRow(price, quantity, update_id))

        for bid in raw_bids:
            price = float(normalize_price_from_drop(bid["quality"])) if is_xrp_pair else float(bid["quality"])
            price = 1 / price

            # Check if taker_pays is string or object
            if isinstance(bid["TakerGets"], str):
                quantity = float(drops_to_xrp(bid["TakerGets"])) if is_xrp_pair else float(bid["TakerGets"])
            else:
                quantity = float(bid["TakerGets"]["value"])

            update_id = int(bid["Sequence"])

            processed_bids.append(OrderBookRow(price, quantity, update_id))

        content = {
            "trading_pair": msg["trading_pair"],
            "update_id": timestamp,
            "bids": processed_bids,
            "asks": processed_asks
        }

        return OrderBookMessage(OrderBookMessageType.SNAPSHOT, content, timestamp=timestamp)

    @classmethod
    def diff_message_from_exchange(cls,
                                   msg: Dict[str, any],
                                   timestamp: Optional[float] = None,
                                   metadata: Optional[Dict] = None) -> OrderBookMessage:
        """
        Creates a diff message with the changes in the order book received from the exchange
        :param msg: the changes in the order book
        :param timestamp: the timestamp of the difference
        :param metadata: a dictionary with extra information to add to the difference data
        :return: a diff message with the changes in the order book notified by the exchange
        """
        pass

    @classmethod
    def trade_message_from_exchange(cls, msg: Dict[str, any], metadata: Optional[Dict] = None):
        """
        Creates a trade message with the information from the trade event sent by the exchange
        :param msg: the trade event details sent by the exchange
        :param metadata: a dictionary with extra information to add to trade message
        :return: a trade message with the details of the trade as provided by the exchange
        """
        if metadata:
            msg.update(metadata)

        return OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": msg["trading_pair"],
            "trade_type": msg["trade_type"],
            "trade_id": msg["trade_id"],
            "update_id": msg["transact_time"],
            "price": msg["price"],
            "amount": msg["fill_quantity"]
        }, timestamp=msg["timestamp"])
