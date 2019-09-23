#!/usr/bin/env python

import time
import hmac
import hashlib
import base64
from typing import Dict
import asyncio
import ujson
import websockets
from websockets.exceptions import ConnectionClosed

class BitroyalAuth:
    def __init__(self, api_key: str, secret_key: str, user_name: str, pass_word: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.user_name = user_name
        self.pass_word = pass_word

    def generate_auth_dict(self) -> Dict[str, any]:
       # nonce = str(int(time.time()* 1000))
        #message = nonce + userid + self.api_key
        #hmac_key = base64.b64decode(self.secret_key)
        #signature_key = hmac.new(hmac_key, message.encode("utf8"), hashlib.sha256)
        #signature_b64 = base64.b64encode(bytes(signature_key.digest())).decode("utf8")

        return ujson.dumps({"UserName": self.user_name, "Password": self.pass_word}).replace('"','\"')

    def get_headers(self, method: str, path_url: str, body: str = "") -> Dict[str, any]:
        header_dict = self.generate_auth_dict(method, path_url, body)
        return {
            "CB-ACCESS-SIGN": header_dict["signature"],
            "CB-ACCESS-TIMESTAMP": header_dict["timestamp"],
            "CB-ACCESS-KEY": header_dict["key"],
            "Content-Type": "application/json",
        }

wss_url = 'wss://apicoinmartprod.alphapoint.com/WSGateway/'

api_url = 'https://apicoinmartprod.alphapoint.com:8443/AP/Authenticate'

getauth = BitroyalAuth("gsyPomAVC8CrTTzG", "QYcTI0HVOhwukrZU0kELHOD5avjZzeYC", "svamol", "#Sush~Viji@84$")

frame = {"m": 0, "i": 0, "n": "AuthenticateUser", "o": ""}

#print(auth.api_key)
auth = getauth.generate_auth_dict()
print(auth)
frame.update(o = auth)
print(frame)
print(auth)

print("create wss connection")
#async with websockets.connect(wss_url) as ws:
#    ws: websockets.WebSocketClientProtocol = ws
#websocket.enableTrace(True)
#wss = create_connection(wss_url)
print(ujson.dumps(frame))
async def hello():
    async with websockets.connect(wss_url) as ws:
        await ws.send(ujson.dumps(frame))
        msg = await ws.recv()
        #msg: str = await asyncio.wait_for(ws.recv(), timeout=30.0)
        print(msg)
asyncio.get_event_loop().run_until_complete(hello())
#print(msg)

#r = requests.post(api_url, headers=headers)
#print("Hit request")
#print(r.json())
