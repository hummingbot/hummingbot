import json
import typing
import functools

import requests

from asyncio import sleep
from dataclasses import dataclass, asdict
from urllib.parse import urlencode
from aiohttp import ClientSession, WSMsgType, WSMessage
from eth_account import Account

from .exceptions import RemoteApiError, TooManyRequestError, ResourceNotFoundError
from ..conf import settings
from ..idex_auth import IdexAuth
from ..types.rest import request
from ..types.rest import response
from ..types.websocket import response as ws_response


def json_default(value):
    # Process enums if they where passed as items
    if hasattr(value, "value"):
        value = value.value
    # Process hex objects
    if hasattr(value, "hex"):
        value = value.hex
    # Process callable
    if callable(value):
        value = value()
    return value


def rest_decorator(call,
                   request_cls: typing.Type = None,
                   response_cls: typing.Type = None,
                   method: str = "get",
                   signed: bool = False):
    def decorator(f):
        @functools.wraps(f)
        async def rest_decorator_wrapper(self, **kwargs):
            return await self.client.request(
                method,
                call,
                kwargs,
                request_cls=request_cls,
                response_cls=response_cls,
                signed=signed
            )
        return rest_decorator_wrapper
    return decorator


class SignedRest:

    @staticmethod
    def get(call: str, request_cls: typing.Type = None, response_cls: typing.Type = None):
        return rest_decorator(call, request_cls, response_cls, signed=True)

    @staticmethod
    def post(call: str, request_cls: typing.Type = None, response_cls: typing.Type = None):
        return rest_decorator(call, request_cls, response_cls, "post", signed=True)

    @staticmethod
    def delete(call: str, request_cls: typing.Type = None, response_cls: typing.Type = None):
        return rest_decorator(call, request_cls, response_cls, "delete", signed=True)


class Rest:

    @staticmethod
    def get(call: str, request_cls: typing.Type = None, response_cls: typing.Type = None):
        return rest_decorator(call, request_cls, response_cls)

    @staticmethod
    def post(call: str, request_cls: typing.Type = None, response_cls: typing.Type = None):
        return rest_decorator(call, request_cls, response_cls, "post")

    @staticmethod
    def delete(call: str, request_cls: typing.Type = None, response_cls: typing.Type = None):
        return rest_decorator(call, request_cls, response_cls, "delete")

    signed = SignedRest()


rest = Rest()


def clean_dict(data):
    if not isinstance(data, (dict, )):
        data = asdict(data)
    return {k: v for k, v in data.items() if v is not None}


def clean_locals(data):
    return {k: v for k, v in data.items() if k != "self"}


WEBSOCKET_MESSAGE_TYPES = {
    # Full response
    "subscriptions": ws_response.WebSocketResponseSubscriptions,

    # Data response
    "l2orderbook": ws_response.WebSocketResponseL2OrderBookShort,
    "error": ws_response.WebSocketResponseErrorData,
    "trades": ws_response.WebSocketResponseTradeShort,
    "orders": ws_response.WebSocketResponseOrderShort,
    "balances": ws_response.WebSocketResponseBalanceShort
}


def handle429(f):

    @functools.wraps(f)
    async def handle429_wrapper(*args, **kwargs):
        max_tries = 3
        while max_tries:
            try:
                return await f(*args, **kwargs)
            except TooManyRequestError:
                # TODO: Dow we need to deal with 5s/10s
                print("THR: Request was throttled! Sleep 10 seconds.")
                await sleep(10)
                continue
            finally:
                max_tries -= 1
        raise TooManyRequestError()
    return handle429_wrapper


@dataclass
class AsyncBaseClient:

    session: ClientSession = None
    auth: IdexAuth = None

    def __post_init__(self):
        if not self.session:
            self.session = ClientSession()

    async def get_auth_token(self, auth: IdexAuth, wallet: str) -> typing.Optional[str]:
        endpoint = settings.rest_api_url.rstrip("/")
        signed_request = auth.generate_auth_dict_for_get(f"{endpoint}/wsToken", params={
            "wallet": wallet
        })
        # resp = await self.session.get(**signed_request)
        # result = await resp.json()
        resp = requests.get(**signed_request)
        result = resp.json()
        if resp.status != 200 or not isinstance(result, dict):
            raise RemoteApiError(
                code="Undefined error",
                message=str(result)
            )
        if "token" in result:
            return result["token"]
        if "code" not in result:
            raise RemoteApiError(
                code=result["code"],
                message=result["message"]
            )

    async def subscribe(self,
                        subscriptions: typing.List[typing.Union[str, typing.Dict]] = None,
                        markets: typing.List[str] = None,
                        method: str = "subscribe",
                        message_cls: typing.Type = None,
                        auth: IdexAuth = None,
                        wallet: str = None):
        """
        TODO: explicit disconnect method
        """
        # Re init session if closed
        if self.session.closed:
            self.session = ClientSession()

        if self.auth:
            wallet = wallet or Account.from_key(self.auth.wallet_private_key).address

        url = settings.ws_api_url
        async with self.session.ws_connect(url) as ws:
            subscription_request = {
                "method": method
            }
            token = await self.get_auth_token(auth, wallet) if auth and wallet else None
            if token:
                subscription_request.update({
                    "token": token
                })

            if markets:
                subscription_request.update({
                    "markets": markets
                })
            if subscriptions:
                subscription_request.update({
                    "subscriptions": subscriptions
                })

            print(f"WSS: {subscription_request}")
            await ws.send_str(json.dumps(subscription_request, default=json_default))
            async for message in ws:   # type: WSMessage
                if message.type in (
                        WSMsgType.CLOSE,
                        WSMsgType.CLOSED,
                        WSMsgType.CLOSING,
                        WSMsgType.ERROR):
                    break
                message = message.json()
                message_type = message.get("type")

                # Get message class
                # We can always override message via input arg
                cls = message_cls or (WEBSOCKET_MESSAGE_TYPES.get(message_type) or "Unhandled")
                # print(f"WSM: from {subscription_request}\n   > {cls.__name__}({message})")

                if "type" not in message or message["type"] not in WEBSOCKET_MESSAGE_TYPES:
                    raise ValueError(f"Unable to handle message {message}")
                # Get data block
                message = message["data"] if "data" in message else message
                # Make dataclass
                if cls:
                    message = cls(**message)
                yield message

    @handle429
    async def request(self,
                      method: str,
                      endpoint: str,
                      data: typing.Union[dict, typing.Any] = None,
                      request_cls: typing.Type = None,
                      response_cls: typing.Type = None,
                      signed: bool = False,
                      wallet_signature: str = None):

        # Re init session if closed
        if self.session.closed:
            self.session = ClientSession()

        # Check auth
        if signed and not self.auth:
            raise Exception("IdexAuth instance required, auth attribute was not inited")

        if request_cls and isinstance(data, dict):
            data = request_cls(**data)

        # Init session
        url = f"{settings.rest_api_url}/{endpoint.lstrip('/')}"
        data = clean_dict(data) if data else None
        headers = {
            "Content-Type": "application/json"
        }
        body = None

        if signed:
            signed_payload = self.auth.generate_auth_dict(
                method,
                url,
                data if method == "get" else None,
                data if method != "get" else None,
                wallet_signature=wallet_signature
            )
            url = signed_payload["url"]
            headers = signed_payload["headers"]
            body = signed_payload.get("body")
        elif method == "get" and data:
            url = f"{url}?{urlencode(data)}"
        else:
            body = json.dumps(data, default=json_default)

        async with self.session as session:
            try:
                # resp = await session.request(
                #     method, url, headers=headers, data=body
                # )
                if session is None:
                    print('No Session')
                if method.lower() == "get":
                    resp = requests.get(url, headers=headers, data=body)
                elif method.lower() == "post":
                    resp = requests.post(url, headers=headers, data=body)
                elif method.lower() == "delete":
                    resp = requests.delete(url, headers=headers, data=body)
                status = resp.status_code
                # Raise 429
                if status == 429:
                    raise TooManyRequestError()
                if status == 404:
                    raise ResourceNotFoundError()
                # Raise if not 200
                if status != 200:
                    # resp_body = await resp.content.read()
                    print(f"Response error: {resp.json()}")
                    raise RemoteApiError(
                        code="RESPONSE_ERROR",
                        message=f"Got unexpected response with status `{status}` and `{resp.json()}` body"
                    )
                result = resp.json()
                if isinstance(result, dict) and set(result.keys()) == {"code", "message"}:
                    raise RemoteApiError(
                        code=result["code"],
                        message=result["message"]
                    )
                # print(f"RESULT: {method.upper()}: {url} with {body}\n {json.dumps(result, indent=2)}")
                if response_cls and isinstance(result, list):
                    return [response_cls(**obj) for obj in result]
                elif response_cls and isinstance(result, dict):
                    return response_cls(**result)
                else:
                    return result
            except Exception as e:
                print(f'Request exception... {method} {url} error: {e}')
                raise e


class AsyncIdexClient(AsyncBaseClient):

    market: "Market" = None
    public: "Public" = None
    trade: "Trade" = None
    user: "User" = None

    def __post_init__(self):
        super(AsyncIdexClient, self).__post_init__()
        for cls in [Market, Public, Trade, User]:
            setattr(
                self,
                cls.__name__.lower(),
                cls(client=self)  # type: EndpointGroup
            )


@dataclass
class EndpointGroup:

    client: AsyncIdexClient


@dataclass
class Public(EndpointGroup):

    @rest.get("ping")
    async def get_ping(self) -> dict:
        pass

    @rest.get("time", response_cls=response.RestResponseTime)
    async def get_time(self) -> response.RestResponseTime:
        pass

    @rest.get("exchange", response_cls=response.RestResponseExchangeInfo)
    async def get_exchange(self) -> response.RestResponseExchangeInfo:
        pass

    @rest.get("assets", response_cls=response.RestResponseAsset)
    async def get_assets(self) -> typing.List[response.RestResponseAsset]:
        pass

    @rest.get("markets", response_cls=response.RestResponseMarket)
    async def get_markets(self) -> typing.List[response.RestResponseMarket]:
        pass


@dataclass
class Market(EndpointGroup):

    @rest.get("tickers", request.RestRequestFindMarkets, response.RestResponseTicker)
    async def get_tickers(self, *,
                          market: typing.Optional[str] = None,
                          regionOnly: typing.Optional[bool] = None) -> typing.List[response.RestResponseTicker]:
        pass

    # @rest.get("candles", request.RestRequestFindCandles, response.RestResponseCandle)
    # async def get_candles(self, *,
    #                       market: str,
    #                       interval: request.CandleInterval,
    #                       start: typing.Optional[int] = None,
    #                       end: typing.Optional[int] = None,
    #                       limit: typing.Optional[int] = None) -> typing.List[response.RestResponseCandle]:
    #     pass

    @rest.get("trades", request.RestRequestFindTrades, response.RestResponseTrade)
    async def get_trades(self, *,
                         market: str,
                         start: typing.Optional[int] = None,
                         end: typing.Optional[int] = None,
                         limit: typing.Optional[int] = None,
                         fromId: typing.Optional[str] = None) -> typing.List[response.RestResponseTrade]:
        pass

    @rest.get("orderbook", request.RestRequestOrderBook, response.RestResponseOrderBook)
    async def get_orderbook(self, *,
                            market: str,
                            level: typing.Optional[int] = 1,
                            limit: typing.Optional[int] = 50) -> response.RestResponseOrderBook:
        pass


@dataclass
class Trade(EndpointGroup):

    @rest.signed.post("orders", request.RestRequestCreateOrderBody, response.RestResponseOrder)
    async def create_order(self,
                           parameters: request.RestRequestOrder) -> response.RestResponseOrder:
        pass

    @rest.signed.get("orders", request.RestRequestFindOrders, response.RestResponseOrder)
    async def get_orders(self,
                         wallet: str,
                         nonce: str,
                         orderId: str) -> typing.Union[typing.List[response.RestResponseOrder], response.RestResponseOrder]:
        pass

    @rest.signed.delete("orders", request.RestRequestCancelOrdersBody, response.RestResponseCanceledOrderItem)
    async def cancel_order(self,
                           parameters: request.RestRequestCancelOrder) -> response.RestResponseCanceledOrder:
        pass


@dataclass
class User(EndpointGroup):

    @rest.signed.get("balances", request.RestRequestFindBalances, response.RestResponseBalance)
    async def balances(self,
                       wallet: str,
                       asset: typing.Optional[str] = None) -> typing.List[response.RestResponseBalance]:
        pass

    @rest.signed.get("wallets", response_cls=response.RestResponseWallet)
    async def wallets(self) -> typing.List[response.RestResponseWallet]:
        pass

    async def associate_wallet(self, nonce: str, wallet_address: str, wallet_signature: str) -> typing.List[response.RestResponseAssociateWallet]:
        return await self.client.request(
            method="POST",
            endpoint="wallets",
            data={
                "parameters": {
                    "nonce": nonce,
                    "wallet": wallet_address,
                },
            },
            signed=True,
            wallet_signature=wallet_signature
        )
