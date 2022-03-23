from dataclasses import dataclass
from decimal import Decimal
import logging
import time
from typing import (
    Optional,
    Dict,
    NamedTuple,
    cast,
)

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.logger.logger import HummingbotLogger
from .exchange_base import ExchangeBase

MAINNET_NETWORKS = {
    "mainnet", "avalanche"
}


class GatewayPriceShimKey(NamedTuple):
    connector_name: str
    chain: str
    network: str
    trading_pair: str


@dataclass
class GatewayPriceShimEntry:
    from_exchange: str
    from_trading_pair: str
    to_connector_name: str
    to_chain: str
    to_network: str
    to_trading_pair: str


@dataclass
class GatewayPriceDeltaEntry:
    connector_name: str
    chain: str
    network: str
    trading_pair: str
    delta: Decimal
    end_timestamp: float


class GatewayPriceShim:
    _gps_logger: Optional[HummingbotLogger]
    _shared_instance: Optional["GatewayPriceShim"]
    _shim_entries: Dict[GatewayPriceShimKey, GatewayPriceShimEntry]
    _delta_entries: Dict[GatewayPriceShimKey, GatewayPriceDeltaEntry]

    def __init__(self):
        self._shim_entries = {}
        self._delta_entries = {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._gps_logger is not None:
            cls._gps_logger = cast(HummingbotLogger, logging.getLogger(__name__))
        return cls._gps_logger

    @classmethod
    def get_instance(cls) -> "GatewayPriceShim":
        if cls._shared_instance is None:
            cls._shared_instance = GatewayPriceShim()
        return cls._shared_instance

    def patch_prices(
            self,
            from_exchange: str,
            from_trading_pair: str,
            to_connector_name: str,
            to_chain: str,
            to_network: str,
            to_trading_pair: str
    ):
        if to_network in MAINNET_NETWORKS:
            raise ValueError("Cannot install price shim to non-testnets.")

        key: GatewayPriceShimKey = GatewayPriceShimKey(
            connector_name=to_connector_name,
            chain=to_chain,
            network=to_network,
            trading_pair=to_trading_pair,
        )
        self._shim_entries[key] = GatewayPriceShimEntry(
            from_exchange=from_exchange,
            from_trading_pair=from_trading_pair,
            to_connector_name=to_connector_name,
            to_chain=to_chain,
            to_network=to_network,
            to_trading_pair=to_trading_pair
        )

    def apply_price_delta(
            self,
            connector_name: str,
            chain: str,
            network: str,
            trading_pair: str,
            delta: Decimal,
            duration_seconds: float = 60):
        if network in MAINNET_NETWORKS:
            raise ValueError("Cannot install price shim to non-testnets.")

        key: GatewayPriceShimKey = GatewayPriceShimKey(
            connector_name=connector_name,
            chain=chain,
            network=network,
            trading_pair=trading_pair,
        )
        if key not in self._shim_entries:
            raise ValueError(f"The trading pair {trading_pair} on {chain}/{network}/{connector_name} has not had "
                             f"price shim installed yet.")
        self._delta_entries[key] = GatewayPriceDeltaEntry(
            connector_name=connector_name,
            chain=chain,
            network=network,
            trading_pair=trading_pair,
            delta=delta,
            end_timestamp=time.time() + duration_seconds
        )

    async def get_connector_price(
            self,
            connector_name: str,
            chain: str,
            network: str,
            trading_pair: str,
            is_buy: bool,
            amount: Decimal) -> Optional[Decimal]:
        key: GatewayPriceShimKey = GatewayPriceShimKey(
            connector_name=connector_name,
            chain=chain,
            network=network,
            trading_pair=trading_pair
        )
        if key not in self._shim_entries:
            return None

        shim_entry: GatewayPriceShimEntry = self._shim_entries[key]
        exchange_market: Optional[ExchangeBase] = HummingbotApplication.main_application().markets.get(
            shim_entry.from_exchange
        )
        if exchange_market is None:
            self.logger().warning(f"Gateway price shim failure: "
                                  f"reference exchange market '{shim_entry.from_exchange}' not found. "
                                  f"Going to use on-chain prices instead.")
            return None

        exchange_price: Decimal = await exchange_market.get_quote_price(
            shim_entry.from_trading_pair,
            is_buy,
            amount
        )
        if key in self._delta_entries:
            delta_entry: GatewayPriceDeltaEntry = self._delta_entries[key]
            now: float = time.time()
            if now <= delta_entry.end_timestamp:
                exchange_price += delta_entry.delta
            else:
                del self._delta_entries[key]
        return exchange_price
