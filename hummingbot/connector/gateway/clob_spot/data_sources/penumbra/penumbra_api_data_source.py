import asyncio
from pprint import pprint
from typing import Any, Dict, List, Optional

from aiohttp import ClientSession
from penumbra_constants import TOKEN_ADDRESS_MAP, TOKEN_SYMBOL_MAP

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.logger import HummingbotLogger


class PenumbraAPIDataSource():
    """An interface class to the Penumbra blockchain.
    """

    _logger: Optional[HummingbotLogger] = None

    def __init__(self,
                 connector_spec: Dict[str, Any],
                 client_config_adaptor: ClientConfigAdapter,
                 shared_client: Optional[ClientSession] = None,
                 connection_secure: Optional[bool] = True):
        self._client_config = client_config_adaptor
        self._chain = "penumbra"
        self._network = connector_spec["network"]
        self._shared_client = shared_client
        self._connection_secure = connection_secure
        self._gateway = self._get_gateway_instance()

        # self.viewProtocolServiceClient

    def get_supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER]

    def _get_gateway_instance(self) -> GatewayHttpClient:
        if self._shared_client is not None:
            GatewayHttpClient._shared_client = self._shared_client
        GatewayHttpClient.base_url = "http://{}:{}".format(
            self._client_config.gateway.gateway_api_host,
            self._client_config.gateway.gateway_api_port)

        gateway_instance = GatewayHttpClient.get_instance(
            client_config_map=self._client_config)
        return gateway_instance

    async def get_gateway_status(self):
        return await self._gateway.get_gateway_status()

    async def get_all_unique_market_assets(self):
        markets = await self._gateway.get_clob_markets(chain=self._chain,
                                                       connector=self._chain,
                                                       network=self._network)
        '''Example market item:
        {'data': {'phi': {'component': {'fee': 0, 'p': {'lo': 2000000, 'hi': 0}, 'q': {'lo': 2000000, 'hi': 0}}, 'pair': {'asset1': {'inner': 'HW2Eq3UZVSBttoUwUi/MUtE7rr2UU7/UH500byp7OAc=', 'altBech32m': '', 'altBaseDenom': ''}, 'asset2': {'inner': 'KeqcLzNx9qSH5+lcJHBB9KNW+YPrBk5dKzvPMiypahA=', 'altBech32m': '', 'altBaseDenom': ''}}}, 'nonce': 'wT+Ls09aP7WBmihIok4SROLyAprx0Va4rJsqmzrqYlU=', 'state': {'state': 3}, 'reserves': {'r1': {'lo': 2000000, 'hi': 0}, 'r2': {'lo': 0, 'hi': 0}}, 'closeOnFill': False}}
        '''
        markets = markets['markets']
        market_assets = {}
        undefined_assets = set()

        for market in markets:
            assetAddress1 = market['data']['phi']['pair']['asset1']['inner']
            assetAddress2 = market['data']['phi']['pair']['asset2']['inner']

            if assetAddress1 not in TOKEN_ADDRESS_MAP:
                undefined_assets.add(assetAddress1)
                continue
            if assetAddress2 not in TOKEN_ADDRESS_MAP:
                undefined_assets.add(assetAddress2)
                continue

            token1Symbol = TOKEN_ADDRESS_MAP[assetAddress1]['symbol']
            token2Symbol = TOKEN_ADDRESS_MAP[assetAddress2]['symbol']

            market_assets[token1Symbol] = TOKEN_SYMBOL_MAP[token1Symbol]
            market_assets[token2Symbol] = TOKEN_SYMBOL_MAP[token2Symbol]

        print("Assets not in token config: ", undefined_assets)

        return market_assets

    async def get_all_market_metadata(self):
        markets = await self._gateway.get_clob_markets(chain=self._chain,
                                                       connector=self._chain,
                                                       network=self._network)
        '''Example market item:
        {'data': {'phi': {'component': {'fee': 0, 'p': {'lo': 2000000, 'hi': 0}, 'q': {'lo': 2000000, 'hi': 0}}, 'pair': {'asset1': {'inner': 'HW2Eq3UZVSBttoUwUi/MUtE7rr2UU7/UH500byp7OAc=', 'altBech32m': '', 'altBaseDenom': ''}, 'asset2': {'inner': 'KeqcLzNx9qSH5+lcJHBB9KNW+YPrBk5dKzvPMiypahA=', 'altBech32m': '', 'altBaseDenom': ''}}}, 'nonce': 'wT+Ls09aP7WBmihIok4SROLyAprx0Va4rJsqmzrqYlU=', 'state': {'state': 3}, 'reserves': {'r1': {'lo': 2000000, 'hi': 0}, 'r2': {'lo': 0, 'hi': 0}}, 'closeOnFill': False}}
        '''
        markets = markets['markets']
        markets_metadata = {}

        for market in markets:
            assetAddress1 = market['data']['phi']['pair']['asset1']['inner']
            assetAddress2 = market['data']['phi']['pair']['asset2']['inner']

            if assetAddress1 not in TOKEN_ADDRESS_MAP:
                token1Symbol = assetAddress1
            else:
                token1Symbol = TOKEN_ADDRESS_MAP[assetAddress1]['symbol']

            if assetAddress2 not in TOKEN_ADDRESS_MAP:
                token2Symbol = assetAddress2
            else:
                token2Symbol = TOKEN_ADDRESS_MAP[assetAddress2]['symbol']

            pair = f'{token1Symbol}-{token2Symbol}'

            # TODO: Add in more metadata as is needed
            if pair not in markets_metadata:
                markets_metadata[pair] = {
                    "positions_found": 1
                }
            else:
                markets_metadata[pair]["positions_found"] += 1

        return markets_metadata

    async def get_markets(self, trading_pairs: Optional[List[str]] = None):
        markets = await self._gateway.get_clob_markets(chain=self._chain,
                                                       connector=self._chain,
                                                       network=self._network)

        if trading_pairs is None:
            return markets

        # network = markets['network']
        # timestamp = markets['timestamp']
        # latency = markets['latency']
        markets: list = markets['markets']
        return_list = []

        # Make sure all trading pairs are supported
        for pair in trading_pairs:
            if pair[0] not in TOKEN_SYMBOL_MAP:
                raise ValueError(
                    f"{pair[0]} is not defined in constant token config.")
            if pair[1] not in TOKEN_SYMBOL_MAP:
                raise ValueError(
                    f"{pair[1]} is not defined in constant token config.")

        # Filter out markets that are not in trading pairs
        for market in markets:
            assetAddress1 = market['data']['phi']['pair']['asset1']['inner']
            assetAddress2 = market['data']['phi']['pair']['asset2']['inner']

            if assetAddress1 not in TOKEN_ADDRESS_MAP:
                token1Symbol = assetAddress1
            else:
                token1Symbol = TOKEN_ADDRESS_MAP[assetAddress1]['symbol']

            if assetAddress2 not in TOKEN_ADDRESS_MAP:
                token2Symbol = assetAddress2
            else:
                token2Symbol = TOKEN_ADDRESS_MAP[assetAddress2]['symbol']

            if [token1Symbol, token2Symbol] in trading_pairs:
                return_list.append(market)

        return return_list


async def main():
    config_map = ClientConfigMap()
    config_map.gateway.gateway_api_host = "localhost"
    config_map.gateway.gateway_api_port = 15888
    sharedClient = ClientSession()

    connector = PenumbraAPIDataSource(
        connector_spec={
            "network": "testnet",
        },
        client_config_adaptor=ClientConfigAdapter(hb_config=config_map),
        shared_client=sharedClient,
        connection_secure=False,
    )
    print("Availible markets assets: ")
    pprint(await connector.get_all_unique_market_assets())

    print("Markets metadata: ")
    pprint(await connector.get_all_market_metadata())

    trading_pairs = [["cube", "penumbra"]]
    print("Looking for trading pairs: ", trading_pairs)
    pprint(await connector.get_markets(trading_pairs=trading_pairs))

    print("---end---")


if __name__ == "__main__":
    asyncio.run(main())

# Resources:
# Working torwards https://hummingbot.org/strategies/avellaneda-market-making/
# https://hummingbot.org/developers/strategies/tutorial/#what-youll-learn
# https://www.youtube.com/watch?v=ZbkkGvB-fis
# M1 & M2 Chip Setup https://hummingbot.org/installation/mac/#conda-and-apple-m1m2-chips

# Installation command copypasta

'''
conda activate hummingbot
./install
./compile
./start

'''
