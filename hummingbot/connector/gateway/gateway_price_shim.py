import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, NamedTuple, Optional, cast

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.logger.logger import HummingbotLogger


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
    """
    Developer / QA tool for modifying the apparent prices on DEX connectors (e.g. uniswap) during integration tests.

    When the gateway price shim is enabled for a particular DEX trading pair (e.g. "WETH-DAI" on uniswap), the apparent
    price on the DEX will follow the prices on a different trading pair on another exchange (e.g. "ETH-USDT" on
    Binance). The price shim then exposes a function (`apply_price_delta()`) which allows the developer to modify the
    apparent prices on the DEX trading pair during live trading. This means the developer can manually control and
    inject arbitrage opportunities in an amm_arb trading session, for carrying out integration tests.

    How to use:

    1. Set up an amm_arb strategy config that trades between a testnet trading pair (e.g. "WETH-DAI" on Uniswap Kovan),
       and a corresponding trading pair on a paper trading exchange (e.g. "ETH-USDT" on Binance paper trade).
    2. Set the `debug_price_shim` parameter of the strategy config to true.
    3. Start the strategy.
    4. Observe that the apparent AMM prices will follow the paper trading exchange prices.
    5. Inject price deltas to the AMM prices by going to the debug console, and issuing the following:

    ```
    from hummingbot.connector.gateway_price_shim import GatewayPriceShim
    from decimal import Decimal
    GatewayPriceShim.get_instance().apply_price_delta("uniswap", "ethereum", "kovan", "WETH-DAI", Decimal(40))
    ```

    6. Observe that the apparent AMM prices is increased by the delta amount, and the amm_arb strategy will start
       issuing arbitrage trades.
    7. Price delta values can be negative if you want to generate buy orders on the AMM side.

    """
    _gps_logger: Optional[HummingbotLogger] = None
    _shared_instance: Optional["GatewayPriceShim"] = None
    _shim_entries: Dict[GatewayPriceShimKey, GatewayPriceShimEntry]
    _delta_entries: Dict[GatewayPriceShimKey, GatewayPriceDeltaEntry]

    def __init__(self):
        self._shim_entries = {}
        self._delta_entries = {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._gps_logger is None:
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

    def has_price_shim(self, connector_name: str, chain: str, network: str, trading_pair: str) -> bool:
        key: GatewayPriceShimKey = GatewayPriceShimKey(
            connector_name=connector_name,
            chain=chain,
            network=network,
            trading_pair=trading_pair
        )
        return key in self._shim_entries
