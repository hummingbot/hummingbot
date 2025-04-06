import asyncio
import json
import os

import aiohttp

OFAC_LIST_URL = (
    "https://raw.githubusercontent.com/InjectiveLabs/injective-lists/"
    "refs/heads/master/json/wallets/ofacAndRestricted.json"
)
OFAC_LIST_FILENAME_DEFAULT = "ofac.json"
OFAC_LIST_FILENAME = OFAC_LIST_FILENAME_DEFAULT


class OfacChecker:
    def __init__(self):
        self._ofac_list_path = self.get_ofac_list_path()
        try:
            with open(self._ofac_list_path, "r") as f:
                self._ofac_list = set(json.load(f))
        except Exception as e:
            raise Exception(
                f"Error parsing OFAC list. Please, download it by running python3 pyinjective/ofac_list.py ({e})"
            )

    @classmethod
    def get_ofac_list_path(cls):
        return os.path.join(os.path.dirname(__file__), OFAC_LIST_FILENAME)

    @classmethod
    async def download_ofac_list(cls):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(OFAC_LIST_URL) as response:
                    response.raise_for_status()
                    text_content = await response.text()
                    ofac_list = json.loads(text_content)
                    ofac_file_path = cls.get_ofac_list_path()
                    with open(ofac_file_path, "w") as f:
                        json.dump(ofac_list, f, indent=2)
                        f.write("\n")
                    return
            except Exception as e:
                raise Exception(f"Error fetching OFAC list: {e}")

    def is_blacklisted(self, address: str) -> bool:
        return address in self._ofac_list


async def main():
    await OfacChecker.download_ofac_list()


if __name__ == "__main__":
    asyncio.run(main())
