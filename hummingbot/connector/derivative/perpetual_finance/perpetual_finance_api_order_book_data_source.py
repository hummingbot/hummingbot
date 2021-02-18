import aiohttp
from typing import List
import json
import ssl

from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.connector.derivative.perpetual_finance.perpetual_finance_utils import convert_from_exchange_trading_pair
from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH


class PerpetualFinanceAPIOrderBookDataSource:
    @staticmethod
    async def fetch_trading_pairs() -> List[str]:
        ssl_ctx = ssl.create_default_context(cafile=GATEAWAY_CA_CERT_PATH)
        ssl_ctx.load_cert_chain(GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH)
        conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
        client = aiohttp.ClientSession(connector=conn)

        base_url = f"https://{global_config_map['gateway_api_host'].value}:" \
                   f"{global_config_map['gateway_api_port'].value}/perpfi/"
        response = await client.get(base_url + "pairs")
        parsed_response = json.loads(await response.text())
        if response.status != 200:
            err_msg = ""
            if "error" in parsed_response:
                err_msg = f" Message: {parsed_response['error']}"
            raise IOError(f"Error fetching pairs from gateway. HTTP status is {response.status}.{err_msg}")
        pairs = parsed_response.get("pairs", [])
        if "error" in parsed_response or len(pairs) == 0:
            raise Exception(f"Error: {parsed_response['error']}")
        else:
            status = await client.get(base_url)
            status = json.loads(await status.text())
            loadedMetadata = status["loadedMetadata"]
            while (not loadedMetadata):
                resp = await client.get(base_url + "load-metadata")
                resp = json.loads(await resp.text())
                loadedMetadata = resp.get("loadedMetadata", False)
                return PerpetualFinanceAPIOrderBookDataSource.fetch_trading_pairs()
        trading_pairs = []
        for pair in pairs:
            trading_pairs.append(convert_from_exchange_trading_pair(pair))
        return trading_pairs
