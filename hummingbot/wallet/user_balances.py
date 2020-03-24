from hummingbot.market.binance.binance_market import BinanceMarket
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.client.config.config_crypt import decrypt_config_value
from hummingbot.client.config.in_memory_config_map import in_memory_config_map
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion
import asyncio


class UserBalances:
    __instance = None

    @staticmethod
    def get_instance():
        if UserBalances.__instance is None:
            UserBalances()
        return UserBalances.__instance

    def __init__(self):
        if UserBalances.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            UserBalances.__instance = self
        self._markets = {}
        self._readies = {}

    def add_exchange(self, exchange):
        if exchange == "binance":
            key, secret = UserBalances.get_api_key_secret(exchange)
            if key is not None and secret is not None:
                self._markets[exchange] = BinanceMarket(key, secret)
                self._readies[exchange] = asyncio.Event()
                safe_ensure_future(self._update_balances(exchange))
        else:
            raise NotImplementedError

    async def _update_balances(self, exchange):
        self._readies[exchange].clear()
        await self._markets[exchange]._update_balances()
        self._readies[exchange].set()

    def get_all_balances(self, exchange):
        if exchange not in self._markets or not self._readies[exchange].is_set():
            return None
        return self._markets[exchange].get_all_balances()

    def get_base_amount_per_total(self, exchange, trading_pair):
        base, quote = trading_pair.split("-")
        user_bals = self.get_all_balances(exchange)
        base_amount = user_bals.get(base, 0)
        quote_amount = user_bals.get(quote, 0)
        rate = ExchangeRateConversion.get_instance().convert_token_value_decimal(1, quote, base)
        total_value = base_amount + (quote_amount * rate)
        return None if total_value <= 0 else base_amount / total_value

    @staticmethod
    def get_api_key_secret(exchange):
        api_key_name = f"{exchange}_api_key"
        secret_key_name = f"{exchange}_api_secret"
        api_key = global_config_map.get(api_key_name).value
        api_secret = global_config_map.get(secret_key_name).value
        if api_key is None or api_secret is None:
            password = in_memory_config_map["password"].value
            api_key = decrypt_config_value(global_config_map[api_key_name], password)
            api_secret = decrypt_config_value(global_config_map[secret_key_name], password)
        if api_key is None or api_secret is None:
            return None, None
        return api_key, api_secret
