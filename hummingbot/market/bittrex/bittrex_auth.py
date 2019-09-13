import time
import hmac
import hashlib
from typing import Dict, Any


class BittrexAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(self, url: str, params: Dict[str, Any] = None) -> Dict[str, any]:
        """
        Generates the url and the valid signature to authenticate with the API endpoint
        :param url: String representing the API endpoint
        :param params: Dictionary of all the url parameters to be included in the api request
        :return: Dictionary containing the final 'params' and its corresponding 'signature'
        """

        # Converts params(dict) into a substring to be appended to final url
        def convert_url_params_to_str(params: Dict[str, Any]) -> str:
            param_list = [f"{p}={v}" for (p, v) in params.items()]
            return "&".join(param_list)

        params.update({"apikey": self.api_key, "nonce": int(time.time())})

        url_to_sign = f"{url}&{convert_url_params_to_str(params)}"
        signature = hmac.new(self.secret_key.encode("utf-8"), url_to_sign.encode("utf8"), hashlib.sha512).hexdigest()

        return {"params": params, "headers": {"apisign": signature}}
