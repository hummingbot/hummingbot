"""
https://arrakis.finance/blog/introducing-arrakis-palm

connector_name
chain
network
trading_pair
pool_address
slippage_pct
palm_initial_leftmost_lower_price
palm_position_price_spread
palm_position_amt_scalar_pct
palm_position_levels
"""


from decimal import Decimal
from typing import Dict, List

from pydantic import Field

from hummingbot.connector.gateway.gateway_lp import CLMMPoolInfo
from hummingbot.strategy_v2.controllers import ControllerBase, ControllerConfigBase
from hummingbot.strategy_v2.executors.data_types import ConnectorPair
from hummingbot.strategy_v2.executors.palm_executor.palm_executor import PALMExecutorConfig, PALMTresholdPrice
from hummingbot.strategy_v2.models.executor_actions import CreateExecutorAction, ExecutorAction


class ClmmBootstrapConfig(ControllerConfigBase):
    controller_type: str = "generic"
    controller_name: str = "palm_bootstrap_controller"
    total_amount_quote: Decimal = 0.0  # override this and not use it

    connector_name: str = Field("raydium/clmm")
    chain: str = Field("solana")
    network: str = Field("mainnet-beta")
    trading_pair: str = Field("SOL-USDC")
    pool_address: str = Field(
        default="",
        json_schema_extra={
            "prompt": "Enter the pool address (e.g., 0x1234567890abcdef): ",
        })

    slippage_pct: float = Field(
        default=0.01,
        json_schema_extra={
            "prompt": "Enter the slippage percentage (e.g., 0.01): ",
        })

    palm_position_price_spread: float = Field(
        default=0.1,
        json_schema_extra={
            "prompt": "PALM positions price spreads (e.g. 0.10): ",
            "prompt_on_new": True,
            "is_updatable": True
        }
    )

    palm_initial_leftmost_quote_amt: float = Field(
        default=100,
        json_schema_extra={
            "prompt": "PALM leftmost quote amount to use (e.g. 0.10): ",
            "prompt_on_new": True,
        }
    )

    palm_position_amt_scalar_pct: float = Field(
        default=0.2,
        json_schema_extra={
            "prompt": "Position amount scalar percent for PALM rebalanceing (e.g. 0 to 1) ",
            "prompt_on_new": True,
        }
    )

    palm_position_levels: int = Field(
        default=3,
        json_schema_extra={
            "prompt": "Enter the number of PALM positions (e.g. 3): ",
            "prompt_on_new": True,
        }
    )

    palm_initial_leftmost_lower_price: float = Field(default=0)


class ClmmBootstrap(ControllerBase):
    """
    Base class for controllers.
    """

    @classmethod
    def init_markets(cls, config: ClmmBootstrapConfig):
        connector_chain_network = f"{config.connector_name}_{config.chain}_{config.network}"
        cls.markets = {connector_chain_network: {config.trading_pair}}  # 'raydium/clmm_solana_mainnet-beta':'SOL-USDC'

    def __init__(self, config: ClmmBootstrapConfig, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.config = config
        self.pool_info: CLMMPoolInfo = None
        self.has_set_positions = False
        self.exchange = f"{self.config.connector_name}_{self.config.chain}_{self.config.network}"
        self.initialize_rate_sources()
        self.palm_positions: Dict = None
        self.treshold_price_low = PALMTresholdPrice(treshold_price=0.0)
        self.treshold_price_high = PALMTresholdPrice(treshold_price=0.0)

    def initiate_controller_params(self):
        if not self.pool_info:
            self.logger().info("Pool info not fetched yet. Cannot initiate controller position parameters.")
            return

        # NOTICE palm_positions[1] is the leftmost position
        self.palm_positions = self.build_initial_palm_positions()
        self.update_treshold_prices()

    def build_initial_palm_positions(self) -> Dict:
        self.current_price = self.pool_info.price
        N = self.config.palm_position_levels

        offset_pcnt = 0
        for lvl in range(int(N / 2)):
            offset_pcnt += self.config.palm_position_price_spread
        offset_pcnt += self.config.palm_position_price_spread / 2

        # NOTICE Calculate the leftmost lower price so that the middle position is half illed with base and half with quote 147
        self.config.palm_initial_leftmost_lower_price = self.current_price * (1 - offset_pcnt)

        palm_initial_leftmost_base_amt = self.config.palm_initial_leftmost_quote_amt / self.current_price
        palm_positions = dict[int, Dict[str, float]]()
        palm_positions[1] = {
            "level_id": 1,
            "quote": self.config.palm_initial_leftmost_quote_amt,
            "base": palm_initial_leftmost_base_amt,
            "lower_price": self.config.palm_initial_leftmost_lower_price,
            "upper_price": self.config.palm_initial_leftmost_lower_price * (1 + self.config.palm_position_price_spread)
        }

        for lvl in range(1, N):
            level_id = lvl

            # Build next PALM level
            level_id_next = level_id + 1
            palm_positions[level_id_next] = {
                "level_id": level_id_next,
                "quote": palm_positions[level_id]["quote"] * (1 + self.config.palm_position_amt_scalar_pct),
                "base": palm_positions[level_id]["base"] * (1 + self.config.palm_position_amt_scalar_pct),
                "lower_price": palm_positions[level_id]["upper_price"],
                "upper_price": palm_positions[level_id]["upper_price"] * (1 + self.config.palm_position_price_spread)
            }

        return palm_positions

    def initialize_rate_sources(self):
        self.market_data_provider.initialize_rate_sources([ConnectorPair(connector_name=self.exchange,
                                                                         trading_pair=self.config.trading_pair)])

    def stop(self):
        super().stop()
        self.logger().info("Stopping the controller")

    async def update_processed_data(self):
        """
        This method should be overridden by the derived classes to implement the logic to update the market data
        used by the controller. And should update the local market data collection to be used by the controller to
        take decisions.
        """
        await self.fetch_pool_info()
        if not self.has_set_positions:
            self.initiate_controller_params()

    def determine_executor_actions(self) -> List[ExecutorAction]:
        """
        This method should be overridden by the derived classes to implement the logic to determine the actions
        that the executors should take.
        """
        actions = []
        proposals = self.create_actions_proposal()
        actions.extend(proposals)
        return actions

    async def fetch_pool_info(self):
        """Fetch pool information to get tokens and current price"""
        self.logger().debug(f"Fetching pool info for {self.config.trading_pair} on {self.exchange}")
        try:
            self.pool_info = await self.market_data_provider.connectors[self.exchange].get_pool_info(
                trading_pair=self.config.trading_pair
            )
        except Exception as e:
            self.logger().error(f"Error fetching pool info: {str(e)}")
            return None

    def create_actions_proposal(self) -> List[ExecutorAction]:
        """
        Create actions based on the provided executor handler report.
        """
        create_actions = []
        self.executors_info
        if self.has_set_positions:
            current_price = self.pool_info.price
            N = self.config.palm_position_levels
            
            self.logger().info(f"High price: {self.treshold_price_high.get_treshold_price()}")
            self.logger().info(f"Current price: {current_price}")
            self.logger().info(f"Low price: {self.treshold_price_low.get_treshold_price()}")

            
            if float(current_price) > self.treshold_price_high.get_treshold_price():
                # rebalance up
                for lvl in range(1, N + 1):
                    # We just move the uper and lower prices for the statistics. The real positions need to rebalance the quote and base amts
                    self.palm_positions[lvl] = {
                        "level_id": lvl,
                        "quote": self.palm_positions[lvl]["quote"],  # this never changes
                        "base": self.palm_positions[lvl]["base"],  # this never changes
                        "lower_price": self.palm_positions[lvl]["lower_price"] * (1 + self.config.palm_position_price_spread),  # this grows to next
                        "upper_price": self.palm_positions[lvl]["upper_price"] * (1 + self.config.palm_position_price_spread)  # this grows to next
                    }

                self.update_treshold_prices()
                create_actions.append(self.create_exec_action(self.palm_positions[1]))


            elif float(current_price) < self.treshold_price_low.get_treshold_price():
                # rebalance down
                for lvl in range(1, N + 1):
                    # We just move the uper and lower prices for the statistics. The real positions need to rebalance the quote and base amts
                    self.palm_positions[lvl] = {
                        "level_id": lvl,
                        "quote": self.palm_positions[lvl]["quote"],  # this never changes
                        "base": self.palm_positions[lvl]["base"],  # this never changes
                        "lower_price": self.palm_positions[lvl]["lower_price"] / (1 + self.config.palm_position_price_spread),  # this falls to previous
                        "upper_price": self.palm_positions[lvl]["upper_price"] / (1 + self.config.palm_position_price_spread)  # this falls to previous
                    }

                self.update_treshold_prices()
                create_actions.append(self.create_exec_action(self.palm_positions[N]))

            
            return create_actions

        for k, v in self.palm_positions.items():
            create_actions.append(self.create_exec_action(v))

        self.has_set_positions = True
        return create_actions

    def update_treshold_prices(self):
        self.treshold_price_low.set_treshold_price(
            (self.palm_positions[1]["lower_price"] + self.palm_positions[1]["upper_price"]) / 2
        )

        self.treshold_price_high.set_treshold_price(
            (self.palm_positions[self.config.palm_position_levels]["lower_price"]
             + self.palm_positions[self.config.palm_position_levels]["upper_price"]) / 2
        )

    def create_exec_action(self, palm_position_dict) -> CreateExecutorAction:
        return CreateExecutorAction(
            controller_id=self.config.id,
            executor_config=PALMExecutorConfig(
                connector_name=self.config.connector_name,
                chain=self.config.chain,
                network=self.config.network,
                trading_pair=self.config.trading_pair,
                pool_address=self.config.pool_address,
                upper_price=Decimal(palm_position_dict["upper_price"]),
                lower_price=Decimal(palm_position_dict["lower_price"]),
                quote_amt=Decimal(palm_position_dict["quote"]),
                base_amt=Decimal(palm_position_dict["base"]),
                position_amt_scalar_pct=self.config.palm_position_amt_scalar_pct,
                slippage_pct=float(self.config.slippage_pct),
                treshold_price_low=self.treshold_price_low,
                treshold_price_high=self.treshold_price_high,
                executor_level_id=palm_position_dict["level_id"],
                executors_total_levels=self.config.palm_position_levels
            )
        )

    def to_format_status(self) -> List[str]:
        """
        This method should be overridden by the derived classes to implement the logic to format the status of the
        controller to be displayed in the UI.
        """
        return []
