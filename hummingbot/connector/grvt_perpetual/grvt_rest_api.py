import requests

class GRVTRestAPI:
    def __init__(self, config):
        self.api_key = config.get('api_key')
        self.base_url = 'https://api.grvt.io/v1'

    def initialize(self):
        pass

    def place_order(self, order):
        url = f'{self.base_url}/order'
        data = {
            'symbol': order['symbol'],
            'price': order['price'],
            'quantity': order['quantity'],
            'side': order['side']
        }
        response = requests.post(url, json=data)
        return response.json()