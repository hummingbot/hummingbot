from typing import Dict, List

import aiohttp

from pyinjective.core.token import Token
from pyinjective.utils.logger import LoggerProvider


class TokensFileLoader:
    def load_json(self, json: List[Dict]) -> List[Token]:
        loaded_tokens = []

        for token_info in json:
            token = Token(
                name=token_info["name"],
                symbol=token_info["symbol"],
                denom=token_info["denom"],
                address=token_info.get("address", ""),
                decimals=token_info["decimals"],
                logo=token_info["logo"],
                updated=-1,
            )

            loaded_tokens.append(token)

        return loaded_tokens

    async def load_tokens(self, tokens_file_url: str) -> List[Token]:
        tokens_list = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(tokens_file_url) as response:
                    if response.ok:
                        tokens_list = await response.json(content_type=None)
        except Exception as e:
            LoggerProvider().logger_for_class(logging_class=self.__class__).warning(
                f"there was an error fetching the list of official tokens: {e}"
            )

        return self.load_json(tokens_list)
