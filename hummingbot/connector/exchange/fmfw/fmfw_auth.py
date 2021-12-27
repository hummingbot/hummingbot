from base64 import b64encode
from hashlib import sha256
from time import time
from hmac import HMAC
from urllib.parse import urlsplit


class FmfwAuth:
    def __init__(self, api_key: str, secret_key: str, window: int = None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.window = window

    def __call__(self, r):
        url = urlsplit(r.url)
        message = [r.method, url.path]
        if url.query:
            message.append('?')
            message.append(url.query)
        if r.body:
            message.append(r.body)
        timestamp = str(int(time() * 1000))
        window = str(self.window) if self.window else None
        message.append(timestamp)
        if window:
            message.append(window)
        signature = HMAC(key=self.secret_key.encode(),
                         msg=''.join(message).encode(),
                         digestmod=sha256).hexdigest()
        data = [self.api_key, signature, timestamp]
        data
        if window:
            data.append(window)
        base64_encoded = b64encode(':'.join(data).encode()).decode()
        r.headers['Authorization'] = f'HS256 {base64_encoded}'
        return r
