from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.market.bittrex.bittrex_market import BittrexMarket
from hummingbot.market.coinbase_pro.coinbase_pro_market import CoinbaseProMarket
from hummingbot.market.huobi.huobi_market import HuobiMarket
from hummingbot.market.kucoin.kucoin_market import KucoinMarket
from hummingbot.market.liquid.liquid_market import LiquidMarket
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
from hummingbot.client.settings import EXCHANGES
from hummingbot.client.config.security import Security
from hummingbot.core.utils.async_utils import safe_gather


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
        return market

    @staticmethod
    async def _update_balances(market):
        # Todo: Check first if _account_id is not already set, but the market objects need to expose this property.
        if isinstance(market, HuobiMarket):
            await market._update_account_id()
        elif isinstance(market, KucoinMarket):
            await market._update_account_id()
        await market._update_balances()

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

    async def add_exchange(self, exchange, *api_details):
        try:
            market = UserBalances.connect_market(exchange, *api_details)
            await UserBalances._update_balances(market)
            self._markets[exchange] = market
        except Exception as e:
            return str(e)
        return None

    def all_balances(self, exchange):
        if exchange not in self._markets:
            return None
        return self._markets[exchange].get_all_balances()

    async def update_all_exchanges(self, reconnect=False):
        tasks = []
        updated_exchanges = []
        if reconnect:
            self._markets.clear()
        for exchange in EXCHANGES:
            if exchange in self._markets:
                tasks.append(self._update_balances(self._markets[exchange]))
                updated_exchanges.append(exchange)
            else:
                api_keys = await Security.api_keys(exchange)
                if api_keys:
                    tasks.append(self.add_exchange(exchange, *api_keys.values()))
                    updated_exchanges.append(exchange)
        results = await safe_gather(*tasks)
        return {ex: err_msg for ex, err_msg in zip(updated_exchanges, results)}

    async def all_balances_all_exchanges(self):
        await self.update_all_exchanges()
        return {k: v.get_all_balances() for k, v in self._markets.items()}

    def get_base_amount_per_total(self, exchange, trading_pair):
        base, quote = trading_pair.split("-")
        user_bals = self.all_balances(exchange)
        base_amount = user_bals.get(base, 0)
        quote_amount = user_bals.get(quote, 0)
        rate = ExchangeRateConversion.get_instance().convert_token_value_decimal(1, quote, base)
        total_value = base_amount + (quote_amount * rate)
        return None if total_value <= 0 else base_amount / total_value
