import aiohttp
# import asyncio
# import logging
from decimal import Decimal
from typing import (
    Any,
    Dict,
    List,
    Tuple,
    # Optional
)

from hummingbot.core.event.events import TradeType
from hummingbot.core.utils.async_utils import safe_ensure_future

TOKEN_CONFIGURATIONS_URL = '/api/v3/exchange/tokens'


class LoopringAPITokenConfigurationDataSource():
    """ Gets the token configuration on creation.

        Use LoopringAPITokenConfigurationDataSource.create() to create.
    """

    def __init__(self):
        self._tokenid_lookup: Dict[str, int] = {}
        self._symbol_lookup: Dict[int, str] = {}
        self._token_configurations: Dict[int, Any] = {}
        self._decimals: Dict[int, Decimal] = {}

    @classmethod
    def create(cls):
        configuration_data_source = cls()
        safe_ensure_future(configuration_data_source._configure())

        return configuration_data_source

    async def _configure(self):
        async with aiohttp.ClientSession() as client:
            response: aiohttp.ClientResponse = await client.get(
                f"https://api3.loopring.io{TOKEN_CONFIGURATIONS_URL}"
            )

            if response.status >= 300:
                raise IOError(f"Error fetching active loopring token configurations. HTTP status is {response.status}.")

            response_dict: Dict[str, Any] = await response.json()

            for config in response_dict:
                self._token_configurations[config['tokenId']] = config
                self._tokenid_lookup[config['symbol']] = config['tokenId']
                self._symbol_lookup[config['tokenId']] = config['symbol']
                self._decimals[config['tokenId']] = Decimal(f"10e{-(config['decimals'] + 1)}")

    def get_bq(self, symbol: str) -> List[str]:
        """ Returns the base and quote of a trading pair """
        return symbol.split('-')

    def get_tokenid(self, symbol: str) -> int:
        """ Returns the token id for the given token symbol """
        return self._tokenid_lookup.get(symbol)

    def get_symbol(self, tokenid: int) -> str:
        """Returns the symbol for the given tokenid """
        return self._symbol_lookup.get(tokenid)

    def unpad(self, volume: str, tokenid: int) -> Decimal:
        """Converts the padded volume/size string into the correct Decimal representation
        based on the "decimals" setting from the token configuration for the referenced token
        """
        return Decimal(volume) * self._decimals[tokenid]

    def pad(self, volume: Decimal, tokenid: int) -> str:
        """Converts the volume/size Decimal into the padded string representation for the api
        based on the "decimals" setting from the token configuration for the referenced token
        """
        return str(Decimal(volume) // self._decimals[tokenid])

    def get_config(self, tokenid: int) -> Dict[str, Any]:
        """ Returns the token configuration for the referenced token id """
        return self._token_configurations.get(tokenid)

    def get_tokens(self) -> List[int]:
        return list(self._token_configurations.keys())

    def sell_buy_amounts(self, baseid, quoteid, amount, price, side) -> Tuple[int]:
        """ Returns the buying and selling amounts for unidirectional orders, based on the order
            side, price and amount and returns the padded values.
        """

        quote_amount = amount * price
        padded_amount = int(self.pad(amount, baseid))
        padded_quote_amount = int(self.pad(quote_amount, quoteid))

        if side is TradeType.SELL:
            return {
                "sellToken": {
                    "tokenId": str(baseid),
                    "volume": str(padded_amount)
                },
                "buyToken": {
                    "tokenId": str(quoteid),
                    "volume": str(padded_quote_amount)
                },
                "fillAmountBOrS": False
            }
        else:
            return {
                "sellToken": {
                    "tokenId": str(quoteid),
                    "volume": str(padded_quote_amount)
                },
                "buyToken": {
                    "tokenId": str(baseid),
                    "volume": str(padded_amount)
                },
                "fillAmountBOrS": True
            }
