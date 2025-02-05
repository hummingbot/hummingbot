from decimal import Decimal
from typing import Dict, List, Optional

import aiohttp

from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase


class DenArbitrageStrategy(ScriptStrategyBase):
    markets = {}
    def __init__(self,
                 ooga_booga_api_key: str = "",
                 den_addresses: List[str] = [],
                 connector_name: str = "berachain",
                 network: str = "testnet"  
                 ):
        super().__init__(connectors={})
        self._ooga_booga_api_key = ""
        self._den_addresses = den_addresses
        self._connector_name = connector_name
        self._network = network  
        self._last_prices: Dict[str, Decimal] = {}
        self._den_info: Dict[str, Optional[Dict]] = {}
        self._gateway_client = GatewayHttpClient.get_instance()        

        self.logger().info("init")


    async def fetch_ooga_booga_prices(self):
        """Fetch prices from Ooga Booga API"""
        self.logger().info(self._ooga_booga_api_key)
        if not self._ooga_booga_api_key:
            self.logger().error("Ooga Booga API key is missing!")
            return

        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {self._ooga_booga_api_key}"}
                url = "https://bartio.api.oogabooga.io/v1/prices?currency=USD"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()                                             
                        self._last_prices = {
                            item["address"].lower(): Decimal(str(item["price"])) 
                            for item in data
                        }
                        self.logger().info("************************************************")
                        self.logger().info("Fetched ooga booga prices")
                        self.logger().info(f"Updated prices: {self._last_prices}")
                    else:
                        error_text = await response.text()
                        self.logger().error(f"Failed to fetch prices: {response.status} - {error_text}")
        except aiohttp.ClientError as e:
            self.logger().error(f"Network error fetching prices: {str(e)}")
        except Exception as e:
            self.logger().error(f"Error fetching prices: {str(e)}")
            
    async def get_den_info(self):
        """
        Fetch den information from Arbera API
        """
        try:
            async with aiohttp.ClientSession() as session:
                self.logger().info("Fetching den info from Arbera API...")
                
                async with session.get("https://arbera.io/api/dens") as response:
                    if response.status == 200:
                        data = await response.json()

                        self._den_info = {
                            item["address"] : {
                                "name": item["name"],
                                "symbol": item["symbol"],
                                "backing_token": item["backingToken"],
                                "backing_token_symbol": item["backingTokenSymbol"],
                                "paired_lp_token": item["pairedLpToken"],
                                "paired_lp_token_symbol": item["pairedLpTokenSymbol"],
                                "den_price": Decimal(str(item["denPrice"])),
                                "fair_price": Decimal(str(item["fairPrice"])),
                                "fees": item["fees"],
                                "den_tvl": Decimal(str(item["denTVL"])),
                                "lp_tvl": Decimal(str(item["lpTVL"])),
                                "den_apr": Decimal(str(item["denAPR"])),
                                "lp_apr": Decimal(str(item["lpAPR"])),
                                "cbr": Decimal(str(item["cbr"]))
                            } for item in data
                        }
                        self.logger().info("************************************************")
                        self.logger().info("Fetched den info from Arbera API")
                        self.logger().info(f"Den info: {self._den_info}")
                    else:
                        self.logger().error(f"Failed to fetch den info. Status: {response.status}")
                        error_text = await response.text()
                        self.logger().error(f"Error response: {error_text}")                        
                        
        except Exception as e:
            self.logger().error(f"Error fetching den info: {str(e)}", exc_info=True)
            

    async def check_arbitrage_opportunities(self):
        """Check for arbitrage opportunities across Den tokens"""
        self.logger().info("Checking arbitrage opportunities...")
        
        for den_address, den_data in self._den_info.items():
            try:
                self.logger().info(f"Analyzing {den_data['symbol']} Den...")
                self.logger().info(f"Den address: {den_address}")

                # Get token balances from den_info
                # den_in_lp = Decimal(str(den_data["den_tvl"]))
                # paired_token_in_lp = Decimal(str(den_data["lp_tvl"]))
                
                # Get backing token price from Ooga Booga
                # backing_token = den_data["backing_token"].lower()
                # backing_token_price = self._last_prices.get(backing_token)
                
                # if not backing_token_price:
                #     self.logger().info(f"No market price found for token {backing_token}")
                #     continue

                # Calculate den price 
                # if den_in_lp == 0:
                #     self.logger().info("Den in LP is 0, skipping...")
                #     continue
                
                # If we have 1000 brHONEY and 980 HONEY in the pool:
                # Den price = 980 HONEY / 1000 brHONEY = 0.98 HONEY per brHONEY
                # den_price = paired_token_in_lp * Decimal("10e18") / den_in_lp
                
                # Calculate fair price using CBR (Collateral Backing Ratio)
                # cbr = den_data["cbr"]
                # fair_price = backing_token_price * cbr
                # fair_price = den_data["den_price"]
                
                
                # Check if index is lower (den price <= fair price)
                den_price = den_data["den_price"]
                fair_price = den_data["fair_price"]
                index_lower = den_price <= fair_price                
                self.logger().info(f"Index lower: {index_lower}")
                
                if index_lower:
                    # Check if fair price > den price + buy + unwrap fees + 1%
                    fees = (Decimal(den_data["fees"]["buy"]) + 
                           Decimal(den_data["fees"]["unwrap"]) + 
                           Decimal("100")) / Decimal("10000")
                    fair_price_minimum = den_price * (Decimal("1") + fees)
                    self.logger().info(f"Fair price minimum: {fair_price_minimum}, fees: {fees}")
                    
                    if fair_price < fair_price_minimum:
                        self.logger().info("Fair price is less than minimum price, skipping...")
                        continue
                else:
                    # Check if den price > fair price + sell + wrap fees + 1%
                    fees = (Decimal(den_data["fees"]["sell"]) + 
                           Decimal(den_data["fees"]["wrap"]) + 
                           Decimal("100")) / Decimal("10000")
                    den_price_minimum = fair_price * (Decimal("1") + fees)
                    self.logger().info(f"Den price minimum: {den_price_minimum}, fees: {fees}")
                    
                    if den_price < den_price_minimum:
                        self.logger().info("Den price is less than minimum price, skipping...")
                        continue
                
                # If we get here, we have a valid arbitrage opportunity
                action = "Buy Den, Unwrap, Sell Token" if index_lower else "Buy Token, Wrap, Sell Den"
                self.logger().info(f"Trying to arb: {action}")
                
                trade_sizes = [
                    # Decimal("100") * Decimal("1e18"),
                    # Decimal("40") * Decimal("1e18"),
                    Decimal("10") * Decimal("1e18")
                ]
                
                for trade_size in trade_sizes:
                    try:
                        await self.execute_arbitrage(
                            den_address=den_address,
                            is_buy_from_den=index_lower,
                            trade_size=trade_size,
                            den_price=den_price,
                            fair_price=fair_price
                        )
                        # If execution succeeds, break the loop
                        break
                    except Exception as e:
                        self.logger().error(f"Error arbing den with size {trade_size}: {str(e)}")
                        continue
                        
            except Exception as e:
                self.logger().error(f"Error checking arbitrage for {den_address}: {str(e)}", exc_info=True)

    async def execute_arbitrage(self, den_address: str, is_buy_from_den: bool, 
                              trade_size: Decimal, den_price: Decimal, 
                              fair_price: Decimal):
        """
        Execute the arbitrage trade
        """
        try:
            self.logger().info(f"Preparing arbitrage execution:")
            self.logger().info(f"Trade size: {trade_size}")
            

            self.logger().info(
                f"Would execute arbIndexPrice with:\n"
                f"  den_address: {den_address}\n"
                f"  trade_size: {trade_size}\n"
                f"  is_buy_from_den: {is_buy_from_den}"
            )
            

            await self._gateway_client.execute_arbitrage(
                chain="berachain",
                network="testnet",
                connector="kodiak",
                indexAddress=den_address,
                amount=trade_size,
                indexLower=is_buy_from_den,
                wallet_address="enter wallet address here"
            )
           
                
        except Exception as e:
            self.logger().error(f"Error executing arbitrage: {str(e)}", exc_info=True)
            raise  # Re-raise to try next trade size

    def on_tick(self):        
        safe_ensure_future(self.process_tick())

    async def process_tick(self):
        """
        Async method to handle the actual tick processing
        """
        try:
            self.logger().info(f"Tick at timestamp {self.current_timestamp}")
        
            # await self.fetch_ooga_booga_prices()
            await self.get_den_info()
            await self.check_arbitrage_opportunities()
            
        except Exception as e:
            self.logger().error(f"Error in tick processing: {str(e)}", exc_info=True)


    @property
    def ready_for_trading(self) -> bool:
        return len(self._den_addresses) > 0 and bool(self._ooga_booga_api_key)

    def format_status(self) -> str:
        """Format status output"""
        if not self.ready_for_trading:
            return "Strategy not ready for trading - check API key and den addresses"
        
        lines = []
        lines.extend([
            f"Number of Den addresses monitored: {len(self._den_addresses)}",
            "\nLast known prices:",
        ])
        
        for address, price in self._last_prices.items():
            lines.append(f"  {address}: {price}")
            
        return "\n".join(lines)