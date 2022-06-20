import base64
import hashlib
import hmac
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional


class CoinexAuth:
    """
    Auth class required by CoinEx API
    Learn more at https://github.com/coinexcom/coinex_exchange_api/wiki/012security_authorization
    """
    def __init__(self, api_key: str, secret_key: str):
        self._access_id = api_key
        self._secret = secret_key

    def generate_auth_dict(
        self,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generates authentication headers for auth of REST required by CoinEx
        :param params: request payload
        :return: a dictionary for params and signature to be used
        """
        timestamp = int(time.time() * 1000)
        params = params if params else dict()
        params.update(access_id=self._access_id)
        params.update(tonce=timestamp)
        params = OrderedDict(sorted(params.items()))
        data = "&".join([f"{str(key)}={str(params[key])}" for key in sorted(params)])
        data = data + "&secret_key=" + self._secret
        raw_data = data.encode()
        _signature = hashlib.md5(raw_data).hexdigest().upper()
        return {
            "params": params,
            "signature": _signature,
        }

    def generate_auth_list(
        self,
    ) -> List[Any]:
        """
        Generates signature for auth of websockets required by CoinEx
        :return: a list for use in params
        """
        timestamp = int(time.time() * 1000)
        params: Dict[str, Any] = dict()
        params.update(access_id=self._access_id)
        params.update(tonce=timestamp)
        params = OrderedDict(sorted(params.items()))
        data = "&".join([f"{str(key)}={str(params[key])}" for key in sorted(params)])
        data = data + "&secret_key=" + self._secret
        raw_data = data.encode()
        _signature = hashlib.md5(raw_data).hexdigest().upper()
        return [
            str(self._access_id).upper(),
            str(_signature),
            int(timestamp)
        ]

    def get_headers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates headers required by CoinEx
        :param params: request payload
        :return: a dictionary of auth headers
        """
        header_dict = self.generate_auth_dict(params)
        return {
            "Accept": "application/json",
            "Authorization": header_dict["signature"],
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36",
        }
