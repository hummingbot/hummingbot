from dydx3.helpers.request_helpers import generate_now_iso


class DydxPerpetualAuth:
    def __init__(self, dydx_client):
        self._dydx_client = dydx_client

    def get_ws_auth_params(self):
        ts = generate_now_iso()
        auth_sig = self._dydx_client.sign(
            request_path='/ws/accounts',
            method='GET',
            timestamp=ts,
            data={},
        )
        ws_auth_params = {
            "type": "subscribe",
            "channel": "v3_accounts",
            "accountNumber": self._dydx_client.account_number,
            "apiKey": self._dydx_client.api_credentials['key'],
            "passphrase": self._dydx_client.api_credentials['passphrase'],
            "timestamp": ts,
            "signature": auth_sig
        }

        return ws_auth_params
