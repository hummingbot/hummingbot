from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.market.bittrex.bittrex_market import BittrexMarket
from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket
from hummingbot.market.huobi.huobi_market import HuobiMarket
from hummingbot.market.kucoin.kucoin_market import KucoinMarket
from hummingbot.market.liquid.liquid_market import LiquidMarket
from hummingbot.market.kraken.kraken_market import KrakenMarket
from hummingbot.market.eterbase.eterbase_market import EterbaseMarket
from hummingbot.core.utils.market_mid_price import get_mid_price
from hummingbot.client.settings import EXCHANGES, DEXES
from hummingbot.client.config.security import Security
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.client.config.global_config_map import global_config_map
from typing import Optional, Dict
from decimal import Decimal

from web3 import Web3


class UserBalances:
    __instance = None

    @staticmethod
    def connect_market(exchange, *api_details):
        market = None
        if exchange == "binance":
            market = BinanceMarket(api_details[0], api_details[1])
        elif exchange == "bittrex":
            market = BittrexMarket(api_details[0], api_details[1])
        elif exchange == "coinbase_pro":
            market = CoinbaseProMarket(api_details[0], api_details[1], api_details[2])
        elif exchange == "huobi":
            market = HuobiMarket(api_details[0], api_details[1])
        elif exchange == "kucoin":
            market = KucoinMarket(api_details[0], api_details[2], api_details[1])
        elif exchange == "liquid":
            market = LiquidMarket(api_details[0], api_details[1])
        elif exchange == "kraken":
            market = KrakenMarket(api_details[0], api_details[1])
        elif exchange == "eterbase":
            market = EterbaseMarket(api_details[0], api_details[1], api_details[2])

        return market

    # return error message if the _update_balances fails
    @staticmethod
    async def _update_balances(market) -> Optional[str]:
        try:
            # Todo: Check first if _account_id is not already set, but the market objects need to expose this property.
            if isinstance(market, HuobiMarket):
                await market._update_account_id()
            elif isinstance(market, KucoinMarket):
                await market._update_account_id()
            await market._update_balances()
        except Exception as e:
            return str(e)
        return None

    @staticmethod
    def instance():
        if UserBalances.__instance is None:
            UserBalances()
        return UserBalances.__instance

    def __init__(self):
        if UserBalances.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            UserBalances.__instance = self
        self._markets = {}

    async def add_exchange(self, exchange, *api_details) -> Optional[str]:
        self._markets.pop(exchange, None)
        market = UserBalances.connect_market(exchange, *api_details)
        err_msg = await UserBalances._update_balances(market)
        if err_msg is None:
            self._markets[exchange] = market
        return err_msg

    def all_balances(self, exchange) -> Dict[str, Decimal]:
        if exchange not in self._markets:
            return None
        return self._markets[exchange].get_all_balances()

    async def update_exchange_balance(self, exchange) -> Optional[str]:
        if exchange in self._markets:
            return await self._update_balances(self._markets[exchange])
        else:
            api_keys = await Security.api_keys(exchange)
            if api_keys:
                return await self.add_exchange(exchange, *api_keys.values())
            else:
                return "API keys have not been added."

    # returns error message for each exchange
    async def update_exchanges(self, reconnect=False, exchanges=EXCHANGES) -> Dict[str, Optional[str]]:
        tasks = []
        # We can only update user exchange balances on CEXes, for DEX we'll need to implement web3 wallet query later.
        exchanges = [ex for ex in exchanges if ex not in DEXES]
        if reconnect:
            self._markets.clear()
        for exchange in exchanges:
            tasks.append(self.update_exchange_balance(exchange))
        results = await safe_gather(*tasks)
        return {ex: err_msg for ex, err_msg in zip(exchanges, results)}

    async def all_balances_all_exchanges(self) -> Dict[str, Dict[str, Decimal]]:
        await self.update_exchanges()
        return {k: v.get_all_balances() for k, v in sorted(self._markets.items(), key=lambda x: x[0])}

    async def balances(self, exchange, *symbols) -> Dict[str, Decimal]:
        if await self.update_exchange_balance(exchange) is None:
            results = {}
            for token, bal in self.all_balances(exchange).items():
                matches = [s for s in symbols if s.lower() == token.lower()]
                if matches:
                    results[matches[0]] = bal
            return results

    @staticmethod
    def ethereum_balance() -> Decimal:
        ethereum_wallet = global_config_map.get("ethereum_wallet").value
        ethereum_rpc_url = global_config_map.get("ethereum_rpc_url").value
        web3 = Web3(Web3.HTTPProvider(ethereum_rpc_url))
        balance = web3.eth.getBalance(ethereum_wallet)
        balance = web3.fromWei(balance, "ether")
        return balance

    @staticmethod
    def validate_ethereum_wallet() -> Optional[str]:
        if global_config_map.get("ethereum_wallet").value is None:
            return "Ethereum wallet is required."
        if global_config_map.get("ethereum_rpc_url").value is None:
            return "ethereum_rpc_url is required."
        if global_config_map.get("ethereum_rpc_ws_url").value is None:
            return "ethereum_rpc_ws_url is required."
        if global_config_map.get("ethereum_wallet").value not in Security.private_keys():
            return "Ethereum private key file does not exist or corrupts."
        try:
            UserBalances.ethereum_balance()
        except Exception as e:
            return str(e)
        return None

    @staticmethod
    def base_amount_ratio(exchange, trading_pair, balances) -> Optional[Decimal]:
        try:
            base, quote = trading_pair.split("-")
            base_amount = balances.get(base, 0)
            quote_amount = balances.get(quote, 0)
            price = get_mid_price(exchange, trading_pair)
            total_value = base_amount + (quote_amount / price)
            return None if total_value <= 0 else base_amount / total_value
        except Exception:
            return None
