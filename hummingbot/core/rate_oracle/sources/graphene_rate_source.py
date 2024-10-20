import asyncio
from decimal import Decimal
from typing import Dict, Optional

from metanode.graphene_metanode_client import GrapheneTrustlessClient

from hummingbot.connector.exchange.graphene.graphene_constants import GrapheneConstants
from hummingbot.core.rate_oracle.sources.rate_source_base import RateSourceBase


class GrapheneRateSource(RateSourceBase):
    def __init__(self, domain):
        self.domain = domain
        super().__init__()

    @property
    def name(self) -> str:
        return self.domain

    async def get_prices(self, quote_token: Optional[str] = None) -> Dict[str, Decimal]:
        constants = GrapheneConstants(self.domain)
        metanode = GrapheneTrustlessClient(constants)
        metanode_pairs = metanode.pairs  # DISCRETE SQL QUERY
        await asyncio.sleep(0.01)
        results = {}
        for pair in constants.chain.ALL_PAIRS:
            try:
                self.logger().info(metanode_pairs[pair]["last"])
                results[pair] = Decimal(metanode_pairs[pair]["last"])
            except Exception:
                msg = (
                    "Unexpected error while retrieving rates from Graphene. "
                    f"Check the log file for more info. Trading Pair {pair}"
                )
                self.logger().error(
                    msg,
                    exc_info=True,
                )
        return results
