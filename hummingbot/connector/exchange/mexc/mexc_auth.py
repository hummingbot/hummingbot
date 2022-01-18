#!/usr/bin/env python

import base64
import hashlib
import hmac
from typing import (
    Any,
    Dict, Optional
)

from hummingbot.connector.exchange.mexc import mexc_utils
from urllib.parse import urlencode, unquote


class MexcAuth:
    def __init__(self, api_key: str, secret_key: str):
        self.api_key: str = api_key
        self.secret_key: str = secret_key

    def _sig(self, method, path, original_params=None):
        params = {
            'api_key': self.api_key,
            'req_time': mexc_utils.seconds()
        }
        if original_params is not None:
            params.update(original_params)
        params_str = '&'.join('{}={}'.format(k, params[k]) for k in sorted(params))
        to_sign = '\n'.join([method, path, params_str])
        params.update({'sign': hmac.new(self.secret_key.encode(), to_sign.encode(), hashlib.sha256).hexdigest()})
        if path in ('/open/api/v2/order/cancel', '/open/api/v2/order/query'):
            if 'order_ids' in params:
                params.update({'order_ids': unquote(params['order_ids'])})
            if 'client_order_ids' in params:
                params.update({'client_order_ids': unquote(params['client_order_ids'])})
        return params

    def add_auth_to_params(self,
                           method: str,
                           path_url: str,
                           params: Optional[Dict[str, Any]] = {},
                           is_auth_required: bool = False
                           ) -> Dict[str, Any]:
        uppercase_method = method.upper()
        params = params if params else dict()
        if not is_auth_required:
            params.update({'api_key': self.api_key})
        else:
            params = self._sig(uppercase_method, path_url, params)
        if params:
            path_url = path_url + '?' + urlencode(params)
        return path_url

    def get_signature(self, operation, timestamp) -> str:
        auth = operation + timestamp + self.api_key

        _hash = hmac.new(self.secret_key.encode(), auth.encode(), hashlib.sha256).digest()
        signature = base64.b64encode(_hash).decode()
        return signature

    def generate_ws_auth(self, operation: str):
        # timestamp = str(int(time.time()))
        # return {
        #     "op": operation,  # sub key
        #     "api_key": self.api_key,  #
        #     "sign": self.get_signature(operation, timestamp),  #
        #     "req_time": timestamp  #
        # }
        pass
