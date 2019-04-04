import hmac, hashlib, time, requests, base64, conf
from requests.auth import AuthBase


# Create custom authentication for Exchange
class CoinbaseExchangeAuth(AuthBase):
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase

    def __call__(self, request):
        timestamp = str(time.time())
        message = timestamp + request.method + request.path_url + (request.body.decode("utf8") or '')
        hmac_key = base64.b64decode(self.secret_key)
        signature = hmac.new(hmac_key, message.encode('utf8'), hashlib.sha256)
        signature_b64 = base64.b64encode(bytes(signature.digest())).decode('utf8')

        request.headers.update({
            'CB-ACCESS-SIGN': signature_b64,
            'CB-ACCESS-TIMESTAMP': timestamp,
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        })
        return request


api_url = 'https://api.pro.coinbase.com/'
auth = CoinbaseExchangeAuth(conf.coinbase_pro_api_key, conf.coinbase_pro_secret_key, conf.coinbase_pro_passphrase)

# Place an order
order = {
    'size': 1.0,
    'price': 100.0,
    'side': 'buy',
    'product_id': 'ETHUSDC',
}
r = requests.post(api_url + 'orders', json=order, auth=auth)
print(r.json())
