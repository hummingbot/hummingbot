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

from hummingbot.core.utils.async_utils import safe_ensure_future

TOKEN_CONFIGURATIONS_URL = 'https://api.dydx.exchange/v2/markets'


class DydxAPITokenConfigurationDataSource():
    """ Gets the token configuration on creation.

        Use DydxAPITokenConfigurationDataSource.create() to create.
    """

    def __init__(self):
        self._tokenid_lookup: Dict[str, int] = {}
        self._symbol_lookup: Dict[int, str] = {}
        self._token_configurations: Dict[int, Any] = {}
        self._digits: Dict[int, int] = {}
        self._decimals: Dict[int, Decimal] = {}

    @classmethod
    def create(cls):
        configuration_data_source = cls()
        safe_ensure_future(configuration_data_source._configure())

        return configuration_data_source

    async def _configure(self):
        async with aiohttp.ClientSession() as client:
            response: aiohttp.ClientResponse = await client.get(
                f"{TOKEN_CONFIGURATIONS_URL}"
            )

            if response.status >= 300:
                raise IOError(f"Error fetching active dydx token configurations. HTTP status is {response.status}.")

            response_dict: Dict[str, Any] = await response.json()

            for market, details in response_dict['markets'].items():
                if "baseCurrency" in details:
                    self._token_configurations[details['baseCurrency']['soloMarketId']] = details['baseCurrency']
                    self._token_configurations[details['quoteCurrency']['soloMarketId']] = details['quoteCurrency']
                    self._tokenid_lookup[details['baseCurrency']['currency']] = details['baseCurrency']['soloMarketId']
                    self._tokenid_lookup[details['quoteCurrency']['currency']] = details['quoteCurrency']['soloMarketId']
                    self._symbol_lookup[details['baseCurrency']['soloMarketId']] = details['baseCurrency']['currency']
                    self._symbol_lookup[details['quoteCurrency']['soloMarketId']] = details['quoteCurrency']['currency']
                    self._digits[details['baseCurrency']['soloMarketId']] = int(details['baseCurrency']['decimals'])
                    self._digits[details['quoteCurrency']['soloMarketId']] = int(details['quoteCurrency']['decimals'])
                    self._decimals[details['baseCurrency']['soloMarketId']] = Decimal(f"1e{-(details['baseCurrency']['decimals'])}")
                    self._decimals[details['quoteCurrency']['soloMarketId']] = Decimal(f"1e{-(details['quoteCurrency']['decimals'])}")

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

    def unpad_price(self, price: str, base_id: int, quote_id: int) -> Decimal:
        """Converts the padded price string into the correct Decimal representation
        based on the "decimals" setting from the token configuration for the referenced base and quote.
        """
        return Decimal(price) * Decimal(f"1e{self._digits[base_id] - self._digits[quote_id]}")

    def pad(self, volume: Decimal, tokenid: int) -> str:
        """Converts the volume/size Decimal into the padded string representation for the api
        based on the "decimals" setting from the token configuration for the referenced token
        """
        return str(Decimal(volume) // self._decimals[tokenid])

    def get_tokens(self) -> List[int]:
        return list(self._token_configurations.keys())

    def sell_buy_amounts(self, baseid, quoteid, amount, price, side) -> Tuple[int]:
        """ Returns the buying and selling amounts for unidirectional orders, based on the order
            side, price and amount and returns the padded values.
        """

        padded_amount = self.pad(amount, baseid)
        adjusted_price = price * Decimal(f"1e{self._digits[quoteid] - self._digits[baseid]}")

        return {
            "baseTokenId": baseid,
            "quoteTokenId": quoteid,
            "amount": padded_amount,
            "price": adjusted_price,
        }
