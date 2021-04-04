import aiohttp
import pendulum
import json
import os
import requests
from typing import (
    Optional,
    Dict,
    Any
)
JSON_SETTINGS = 'settings-private.json'
STEX_TOKEN_URL = "https://api3.stex.com/oauth/token"
class StexAuth:
    def __init__(self, access_token:str):
        self.access_token = access_token
        self.user_id = None

    def get_user_id(self):
        headers = {'Content-Type': 'application/json', 'User-Agent': 'stex_python_client'}
        try:
            headers['Authorization'] = 'Bearer {}'.format(self.access_token)
            url = "https://api3.stex.com/profile/info"
            response = requests.get(url,headers=headers)
            profile_data =  response.json()
            return profile_data["data"]["user_id"]
        except Exception as e:
            raise IOError(f"Error fetching user id from {url}. Response:{response.json()}.")

    def generate_auth_dict(self, data: Optional[Dict[str,str]] = None) -> Dict[str, Any]:
        if self.user_id is None:
            self.user_id = self.get_user_id()
        client = {
            'access_token': self.access_token,
            'user_id': self.user_id
        }
        return client
