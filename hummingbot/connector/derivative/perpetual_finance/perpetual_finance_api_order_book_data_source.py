import aiohttp
from typing import List
import json
from typing import Dict

from hummingbot.connector.derivative.perpetual_finance.perpetual_finance_utils import convert_from_exchange_trading_pair


class PerpetualFinanceAPIOrderBookDataSource:
    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        url = "https://metadata.perp.exchange/production.json"
        async with aiohttp.ClientSession() as client:
            response = await client.get(url)
            trading_pairs = []
            parsed_response = json.loads(await response.text())
            contracts = parsed_response["layers"]["layer2"]["contracts"]
            trading_pairs = [convert_from_exchange_trading_pair(contract) for contract in contracts.keys() if contracts[contract]["name"] == "Amm"]
            return trading_pairs

    @classmethod
    async def get_last_traded_prices(cls, trading_pairs: List[str]) -> Dict[str, float]:
        """
        This function doesn't really need to return a value.
        It is only currently used for performance calculation which will in turn use the last price of the last trades
        if None is returned.
        """
        pass
