import logging
import os
from decimal import Decimal
from typing import Dict, List, Optional

import aiohttp
from pydantic import Field

from hummingbot.client.config.config_data_types import BaseClientModel
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PriceType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.event.events import OrderFilledEvent
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

LIFI_API_KEY = "a3a23273-e1cd-40ae-befc-6151971a3349.bd93c98c-9253-4f45-85cc-ea21fd11509e"
IBTC_TOKEN_ADDRESS = "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599"
IBTC_CHAIN_ID = 1

# Pair to seed the orderbook:
# - iBTC-USDC
# - USDC-RLUSD
# - iBTC-RLUSD


async def fetch_token_price_lifi(chain_id: int, token_address: str, timeout: int = 10) -> Optional[Decimal]:
    """
    Fetch token price using li.fi API.

    Args:
        chain_id: Blockchain ID (e.g., 1 for Ethereum, 56 for BSC, 137 for Polygon)
        token_address: Token contract address
        api_key: li.fi API key
        timeout: Request timeout in seconds

    Returns:
        Token price in USD as Decimal, or None if failed

    Example:
        # Get USDC price on Ethereum
        price = await fetch_token_price_lifi(1, "0xA0b86a33E6417c9c87Cf77e13C60d6B6e4Cf4a08", "your_api_key")
    """
    url = "https://li.quest/v1/token"

    params = {"chain": chain_id, "token": token_address}

    headers = {"x-lifi-api-key": LIFI_API_KEY, "Content-Type": "application/json"}

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()

                    # Extract price from response
                    if "priceUSD" in data:
                        price_str = data["priceUSD"]
                        return Decimal(str(price_str))
                    else:
                        logging.warning(f"No priceUSD found in li.fi response for {token_address}")
                        return None

                else:
                    error_text = await response.text()
                    logging.error(f"li.fi API error {response.status}: {error_text}")
                    return None

    except aiohttp.ClientError as e:
        logging.error(f"Network error fetching token price from li.fi: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error fetching token price from li.fi: {e}")
        return None


class SeedOrderbookPMMConfig(BaseClientModel):
    script_file_name: str = os.path.basename(__file__)
    ibtc_order_amount: Decimal = Field(Decimal(0.000001))
    usdc_order_amount: Decimal = Field(Decimal(0.1))
    best_bid_spread: Decimal = Field(Decimal(0.01))
    best_ask_spread: Decimal = Field(Decimal(0.01))
    step_size: Decimal = Field(Decimal(0.01))
    order_levels: int = Field(1)
    order_refresh_time: int = Field(60 * 15)


class SeedOrderbookPMM(ScriptStrategyBase):
    """
    BotCamp Cohort: Sept 2022
    Design Template: https://hummingbot-foundation.notion.site/Simple-PMM-63cc765486dd42228d3da0b32537fc92
    Video: -
    Description:
    The bot will place two orders around the price_source (mid price or last traded price) in a trading_pair on
    exchange, with a distance defined by the ask_spread and bid_spread. Every order_refresh_time in seconds,
    the bot will cancel and replace the orders.
    """

    create_timestamp = 0
    price_source = PriceType.MidPrice
    ibtc_current_price = None
    seed_trading_pairs = ["IBTC-USDC", "USDC-RLUSD", "IBTC-RLUSD"]

    @classmethod
    def init_markets(cls, config: SeedOrderbookPMMConfig):
        cls.markets = {
            "xrpl": {
                "IBTC-USDC",
                "USDC-RLUSD",
                "IBTC-RLUSD",
            }
        }

    def __init__(self, connectors: Dict[str, ConnectorBase], config: SeedOrderbookPMMConfig):
        super().__init__(connectors)
        self.config = config

    def on_tick(self):
        if self.create_timestamp <= self.current_timestamp:
            self.cancel_all_orders()
            safe_ensure_future(self.get_external_ibtc_token_price(IBTC_CHAIN_ID, IBTC_TOKEN_ADDRESS))

            # If ibtc price is not set, skip
            if self.ibtc_current_price is None:
                return

            proposal: List[OrderCandidate] = self.create_proposal()
            proposal_adjusted: List[OrderCandidate] = self.adjust_proposal_to_budget(proposal)
            self.place_orders(proposal_adjusted)
            self.create_timestamp = self.config.order_refresh_time + self.current_timestamp

    def create_proposal(self) -> List[OrderCandidate]:
        orders = []

        # Create orders for each trading pair
        for trading_pair in self.seed_trading_pairs:
            ref_price = self.get_reference_price(trading_pair)

            if ref_price is None:
                self.logger().warning(f"Skipping {trading_pair} - no reference price available")
                continue

            start_buy_price = ref_price * Decimal(1 - self.config.best_bid_spread)
            start_sell_price = ref_price * Decimal(1 + self.config.best_ask_spread)

            # Get the appropriate order amount for this trading pair
            order_amount = self.get_order_amount(trading_pair)

            for i in range(self.config.order_levels):
                # Calculate prices for this level
                level_buy_price = start_buy_price - (i * self.config.step_size * start_buy_price)
                level_sell_price = start_sell_price + (i * self.config.step_size * start_sell_price)

                # Create buy order for this level
                buy_order = OrderCandidate(
                    trading_pair=trading_pair,
                    is_maker=True,
                    order_type=OrderType.LIMIT,
                    order_side=TradeType.BUY,
                    amount=order_amount,
                    price=level_buy_price,
                )
                orders.append(buy_order)

                # Create sell order for this level
                sell_order = OrderCandidate(
                    trading_pair=trading_pair,
                    is_maker=True,
                    order_type=OrderType.LIMIT,
                    order_side=TradeType.SELL,
                    amount=order_amount,
                    price=level_sell_price,
                )
                orders.append(sell_order)

        return orders

    def get_reference_price(self, trading_pair: str) -> Optional[Decimal]:
        """
        Get reference price for different trading pairs based on their characteristics.

        Args:
            trading_pair: The trading pair to get price for

        Returns:
            Reference price in USD or None if unavailable
        """
        if trading_pair == "IBTC-USDC":
            # Use li.fi price for iBTC, denominated in USDC
            return self.ibtc_current_price

        elif trading_pair == "USDC-RLUSD":
            # Stable pair - reference price is 1 USD
            return Decimal("1.0")

        elif trading_pair == "IBTC-RLUSD":
            # Use li.fi price for iBTC, denominated in RLUSD (same as USD since RLUSD ~= USD)
            return self.ibtc_current_price

        else:
            # Fallback to exchange price if available
            try:
                return self.connectors["xrpl"].get_price_by_type(trading_pair, self.price_source)
            except Exception as e:
                self.logger().error(f"Error getting price for {trading_pair}: {e}")
                return None

    def get_order_amount(self, trading_pair: str) -> Decimal:
        """
        Get the appropriate order amount based on the base token of the trading pair.

        Args:
            trading_pair: The trading pair to get order amount for (format: BASE-QUOTE)

        Returns:
            Order amount as Decimal
        """
        # Extract base token from trading pair (before the dash)
        base_token = trading_pair.split("-")[0]

        if base_token == "IBTC":
            # For iBTC as base token, use smaller iBTC amount
            return self.config.ibtc_order_amount
        else:
            # For USD tokens (USDC, RLUSD) as base token, use USD amount
            return self.config.usdc_order_amount

    def adjust_proposal_to_budget(self, proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        proposal_adjusted = self.connectors["xrpl"].budget_checker.adjust_candidates(proposal, all_or_none=True)
        return proposal_adjusted

    def place_orders(self, proposal: List[OrderCandidate]) -> None:
        for order in proposal:
            self.place_order(connector_name="xrpl", order=order)

    def place_order(self, connector_name: str, order: OrderCandidate):
        if order.order_side == TradeType.SELL:
            self.sell(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )
        elif order.order_side == TradeType.BUY:
            self.buy(
                connector_name=connector_name,
                trading_pair=order.trading_pair,
                amount=order.amount,
                order_type=order.order_type,
                price=order.price,
            )

    def cancel_all_orders(self):
        for order in self.get_active_orders(connector_name="xrpl"):
            self.cancel("xrpl", order.trading_pair, order.client_order_id)

    def did_fill_order(self, event: OrderFilledEvent):
        msg = f"{event.trade_type.name} {round(event.amount, 2)} {event.trading_pair} xrpl at {round(event.price, 2)}"
        self.log_with_clock(logging.INFO, msg)
        self.notify_hb_app_with_timestamp(msg)

    async def get_external_ibtc_token_price(self, chain_id: int, token_address: str) -> Optional[Decimal]:
        """
        Example method showing how to use the li.fi price utility.

        Args:
            chain_id: Blockchain ID (1=Ethereum, 56=BSC, 137=Polygon, etc.)
            token_address: Token contract address

        Returns:
            Token price in USD or None if failed
        """

        try:
            price = await fetch_token_price_lifi(chain_id=chain_id, token_address=token_address)

            if price:
                self.logger().info(f"Fetched price for token {token_address} on chain {chain_id}: ${price}")
                self.ibtc_current_price = price
            else:
                self.logger().warning(f"Failed to fetch price for token {token_address} on chain {chain_id}")

        except Exception as e:
            self.logger().error(f"Error fetching external token price: {e}")
