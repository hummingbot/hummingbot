from typing import Any, Dict

from hummingbot.connector.exchange.xago_io import xago_io_constants as CONSTANTS


class XagoIoAuth():
    """
    Auth class required by xago.io API
    Learn more at https://exchange-docs.xago.io/#digital-signature
    """
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def generate_auth_dict(self):
        """
        Generates authentication signature and return it in a dictionary along with other inputs
        :return: a dictionary of request info including the request signature
        """

        # Todo: when using signed requests, create the signature here

        return {
            'policyId': CONSTANTS.POLICY_ID,
            'fields': [
                {
                    'fieldName': 'apiPublicKey', 'fieldValue': self.api_key
                },
                {
                    'fieldName': 'apiSecretKey', 'fieldValue': self.secret_key
                }
            ]
        }

    def get_headers(self, is_auth_required) -> Dict[str, Any]:
        """
        Generates authentication headers required by xago.io
        :return: a dictionary of auth headers
        """

        headers = {
            "Content-Type": 'application/json', 
            'Authorization': 'Bearer ' + CONSTANTS.ACCESS_TOKEN
            } if is_auth_required else {
                "Content-Type": 'application/json'
            }
        
        return headers
