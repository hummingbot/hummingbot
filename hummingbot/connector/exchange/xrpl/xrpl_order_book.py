from typing import Dict, Optional

from xrpl.utils import drops_to_xrp

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

        if metadata:
            msg.update(metadata)

        raw_asks = msg.get("asks", [])
        raw_bids = msg.get("bids", [])
        processed_asks = []
        processed_bids = []

        for ask in raw_asks:

            if "taker_gets_funded" in ask and "taker_pays_funded" in ask:
                """
                If the order is partially funded, the taker_gets_funded and taker_pays_funded fields will be present. We skip unfunded offers.
                """
                if cls.get_amount_from_taker_pays_funded(ask) == 0 or cls.get_amount_from_taker_gets_funded(ask) == 0:
                    continue

                price = cls.get_amount_from_taker_pays_funded(ask) / cls.get_amount_from_taker_gets_funded(ask)
                quantity = cls.get_amount_from_taker_gets_funded(ask)
            else:
                price = cls.get_amount_from_taker_pays(ask) / cls.get_amount_from_taker_gets(ask)
                quantity = cls.get_amount_from_taker_gets(ask)

            update_id = int(ask["Sequence"])

            processed_asks.append(OrderBookRow(price, quantity, update_id))

        for bid in raw_bids:
            if "taker_gets_funded" in bid and "taker_pays_funded" in bid:
                """
                If the order is partially funded, the taker_gets_funded and taker_pays_funded fields will be present. We skip unfunded offers.
                """
                if cls.get_amount_from_taker_pays_funded(bid) == 0 or cls.get_amount_from_taker_gets_funded(bid) == 0:
                    continue

                price = cls.get_amount_from_taker_gets_funded(bid) / cls.get_amount_from_taker_pays_funded(bid)
                quantity = cls.get_amount_from_taker_pays_funded(bid)
            else:
                price = cls.get_amount_from_taker_gets(bid) / cls.get_amount_from_taker_pays(bid)
                quantity = cls.get_amount_from_taker_pays(bid)

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
    def get_amount_from_taker_gets(cls, offer):
        if isinstance(offer["TakerGets"], str):
            return float(drops_to_xrp(offer["TakerGets"]))

        return float(offer["TakerGets"]["value"])

    @classmethod
    def get_amount_from_taker_gets_funded(cls, offer: Dict[str, any]):
        if isinstance(offer["taker_gets_funded"], str):
            return float(drops_to_xrp(offer["taker_gets_funded"]))

        return float(offer["taker_gets_funded"]["value"])

    @classmethod
    def get_amount_from_taker_pays(cls, offer):
        if isinstance(offer["TakerPays"], str):
            return float(drops_to_xrp(offer["TakerPays"]))

        return float(offer["TakerPays"]["value"])

    @classmethod
    def get_amount_from_taker_pays_funded(cls, offer):
        if isinstance(offer["taker_pays_funded"], str):
            return float(drops_to_xrp(offer["taker_pays_funded"]))

        return float(offer["taker_pays_funded"]["value"])

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
            "amount": msg["amount"]
        }, timestamp=msg["timestamp"])
