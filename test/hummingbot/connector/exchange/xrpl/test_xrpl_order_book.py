import unittest

from hummingbot.connector.exchange.xrpl.xrpl_order_book import XRPLOrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessageType


class TestXRPLOrderBook(unittest.TestCase):
    def setUp(self):
        self.xrpl_order_book = XRPLOrderBook()

    def _snapshot_response(self):
        resp = {
            "asks": [
                {
                    "Account": "r9aZRryD8AZzGqQjYrQQuBBzebjF555Xsa",  # noqa: mock
                    "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07FA0FAB195976",  # noqa: mock
                    "BookNode": "0",
                    "Flags": 131072,
                    "LedgerEntryType": "Offer",
                    "OwnerNode": "0",
                    "PreviousTxnID": "373EA7376A1F9DC150CCD534AC0EF8544CE889F1850EFF0084B46997DAF4F1DA",  # noqa: mock
                    "PreviousTxnLgrSeq": 88935730,
                    "Sequence": 86514258,
                    "TakerGets": {
                        "currency": "534F4C4F00000000000000000000000000000000",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                        "value": "91.846106",
                    },
                    "TakerPays": "20621931",
                    "index": "1395ACFB20A47DE6845CF5DB63CF2E3F43E335D6107D79E581F3398FF1B6D612",  # noqa: mock
                    "owner_funds": "140943.4119268388",
                    "quality": "224527.003899327",
                },
                {
                    "Account": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",
                    "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07FA8ECFD95726",  # noqa: mock
                    "BookNode": "0",
                    "Flags": 0,
                    "LedgerEntryType": "Offer",
                    "OwnerNode": "2",
                    "PreviousTxnID": "2C266D54DDFAED7332E5E6EC68BF08CC37CE2B526FB3CFD8225B667C4C1727E1",  # noqa: mock
                    "PreviousTxnLgrSeq": 88935726,
                    "Sequence": 71762354,
                    "TakerGets": {
                        "currency": "534F4C4F00000000000000000000000000000000",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                        "value": "44.527243023",
                    },
                    "TakerPays": "10000000",
                    "index": "186D33545697D90A5F18C1541F2228A629435FC540D473574B3B75FEA7B4B88B",  # noqa: mock
                    "owner_funds": "88.4155435721498",
                    "quality": "224581.6116401958",
                },
            ],
            "bids": [
                {
                    "Account": "rn3uVsXJL7KRTa7JF3jXXGzEs3A2UEfett",  # noqa: mock
                    "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FE48CEADD8471",  # noqa: mock
                    "BookNode": "0",
                    "Flags": 0,
                    "LedgerEntryType": "Offer",
                    "OwnerNode": "0",
                    "PreviousTxnID": "2030FB97569D955921659B150A2F5F02CC9BBFCA95BAC6B8D55D141B0ABFA945",  # noqa: mock
                    "PreviousTxnLgrSeq": 88935721,
                    "Sequence": 74073461,
                    "TakerGets": "187000000",
                    "TakerPays": {
                        "currency": "534F4C4F00000000000000000000000000000000",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                        "value": "836.5292665312212",
                    },
                    "index": "3F41585F327EA3690AD19F2A302C5DF2904E01D39C9499B303DB7FA85868B69F",  # noqa: mock
                    "owner_funds": "6713077567",
                    "quality": "0.000004473418537600113",
                },
                {
                    "Account": "rsoLoDTcxn9wCEHHBR7enMhzQMThkB2w28",
                    "BookDirectory": "C73FAC6C294EBA5B9E22A8237AAE80725E85372510A6CA794F0FE48D021C71F2",  # noqa: mock
                    "BookNode": "0",
                    "Expiration": 772644742,
                    "Flags": 0,
                    "LedgerEntryType": "Offer",
                    "OwnerNode": "0",
                    "PreviousTxnID": "226434A5399E210F82F487E8710AE21FFC19FE86FC38F3634CF328FA115E9574",  # noqa: mock
                    "PreviousTxnLgrSeq": 88935719,
                    "Sequence": 69870875,
                    "TakerGets": "90000000",
                    "TakerPays": {
                        "currency": "534F4C4F00000000000000000000000000000000",
                        "issuer": "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz",
                        "value": "402.6077034840102",
                    },
                    "index": "4D31D069F1E2B0F2016DA0F1BF232411CB1B4642A49538CD6BB989F353D52411",  # noqa: mock
                    "owner_funds": "827169016",
                    "quality": "0.000004473418927600114",
                },
            ],
            "trading_pair": "SOLO-XRP",
        }

        return resp

    def test_snapshot_message_from_exchange(self):
        msg = self._snapshot_response()
        timestamp = 1234567890.0
        metadata = {"source": "XRPL"}

        snapshot_message = self.xrpl_order_book.snapshot_message_from_exchange(msg, timestamp, metadata)

        self.assertEqual(OrderBookMessageType.SNAPSHOT, snapshot_message.type)
        self.assertEqual("SOLO-XRP", snapshot_message.content["trading_pair"])
        self.assertEqual(2, len(snapshot_message.content["bids"]))
        self.assertEqual(2, len(snapshot_message.content["asks"]))
        self.assertEqual(1234567890.0, snapshot_message.timestamp)

    def test_trade_message_from_exchange(self):
        msg = {
            "trading_pair": "XRP-USD",
            "trade_type": "buy",
            "trade_id": "1234",
            "transact_time": 1234567890.0,
            "price": 1.0,
            "amount": 100.0,
            "timestamp": 1234567890.0,
        }

        trade_message = self.xrpl_order_book.trade_message_from_exchange(msg)

        self.assertEqual(OrderBookMessageType.TRADE, trade_message.type)
        self.assertEqual("XRP-USD", trade_message.content["trading_pair"])
        self.assertEqual("buy", trade_message.content["trade_type"])
        self.assertEqual("1234", trade_message.content["trade_id"])
        self.assertEqual(1234567890.0, trade_message.content["update_id"])
        self.assertEqual(1.0, trade_message.content["price"])
        self.assertEqual(100.0, trade_message.content["amount"])
