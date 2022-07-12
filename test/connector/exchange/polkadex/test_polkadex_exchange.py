from decimal import Decimal
from unittest import IsolatedAsyncioTestCase

from hummingbot.connector.exchange.polkadex.polkadex_exchange import PolkadexExchange
from hummingbot.core.data_type.common import TradeType, OrderType


class PolkadexOrderbookTests(IsolatedAsyncioTestCase):
    async def test_place_order(self):
        exchange = PolkadexExchange(polkadex_seed_phrase="crucial expose swim clinic injury deliver save thrive "
                                                         "cabbage erupt cotton butter",
                                    trading_required=True,
                                    trading_pairs=["PDEX-1"])

        await exchange._place_order("HBOT-ORDER_ID", "PDEX-1", Decimal(100.0), TradeType.BUY, OrderType.LIMIT, Decimal(0.4))
