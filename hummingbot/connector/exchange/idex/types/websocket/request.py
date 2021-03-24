# import typing
# from dataclasses import dataclass
#
# from .constants import WEBSOCKET_UNAUTHENTICATED_SUBSCRIPTIONS, WEBSOCKET_AUTHENTICATED_SUBSCRIPTIONS
# from ..enums import CandleInterval
#
#
# WebSocketRequestSubscriptionName = typing.Union[
#     WEBSOCKET_AUTHENTICATED_SUBSCRIPTIONS,
#     WEBSOCKET_UNAUTHENTICATED_SUBSCRIPTIONS
# ]
#
#
# @dataclass
# class WebSocketRequestTickersSubscription:
#     """
#     string name - 'tickers'
#     string markets - array of market symbols
#     """
#     name: typing.Literal['tickers']
#     markets: typing.List[str]
#
#
# @dataclass
# class WebSocketRequestCandlesSubscription:
#     """
#     string name - 'candles'
#     string markets - array of market symbols
#     string interval - candle interval
#     """
#     name: typing.Literal['candles']
#     markets: typing.List[str]
#     interval: CandleInterval
#
#
# @dataclass
# class WebSocketRequestOrdersSubscription:
#     """
#     string name - 'orders'
#     string [wallet] - wallet address
#     """
#     name: typing.Literal['orders']
#     wallet: typing.Optional[str]
#
#
# @dataclass
# class WebSocketRequestBalancesSubscription:
#     name: typing.Literal['balances']
#     wallet: typing.Optional[str]
#
#
# @dataclass
# class WebSocketRequestWallet:
#     """
#     wallet is required and is only handled by the idex-sdk.  It is used to auto generate the required
#     """
#     wallet: str
#
#
# @dataclass
# class AuthTokenWebSocketRequestBalancesSubscription(
#     WebSocketRequestBalancesSubscription,
#     WebSocketRequestWallet):
#     pass
#
#
# @dataclass
# class AuthTokenWebSocketRequestOrdersSubscription(
#     WebSocketRequestOrdersSubscription,
#     WebSocketRequestWallet):
#     pass
#
#
# AuthTokenWebSocketRequestAuthenticatedSubscription = typing.Union[
#     AuthTokenWebSocketRequestBalancesSubscription,
#     AuthTokenWebSocketRequestOrdersSubscription
# ]
#
#
# @dataclass
# class WebSocketRequestTradesSubscription:
#     """
#     string name - 'trades'
#     string[]markets - array of market symbols
#     """
#     name: typing.Literal['trades']
#     markets: typing.List[str]
#
#
# @dataclass
# class WebSocketRequestL1OrderBookSubscription:
#     """
#     string name - 'l1orderbook'
#     string[] markets - array of market symbols
#     """
#     name: typing.Literal['l1orderbook']
#     markets: typing.List[str]
#
#
# @dataclass
# class WebSocketRequestL2OrderBookSubscription:
#     """
#     string name - 'l2orderbook'
#     string[] markets - array of market symbols
#     """
#     name: typing.Literal['l2orderbook']
#     markets: typing.List[str]
#
#
# WebSocketRequestUnauthenticatedSubscription = typing.Union[
#     WebSocketRequestCandlesSubscription,
#     WebSocketRequestL1OrderBookSubscription,
#     WebSocketRequestL2OrderBookSubscription,
#     WebSocketRequestTickersSubscription,
#     WebSocketRequestTradesSubscription,
# ]
#
#
# WebSocketRequestSubscription = typing.Union[
#     AuthTokenWebSocketRequestAuthenticatedSubscription,
#     WebSocketRequestUnauthenticatedSubscription
# ]
# """
#
#
# /**
#  * @typedef {Object} AuthTokenWebSocketRequestBalancesSubscription
#  * @property {'balances'} name - The name of the subscription
#  * @property {string} wallet -
#  *  Balances subscription with `wallet` attribute, which is fed to the `websocketAuthTokenFetch`
#  *  function when needed to get an updated `wsToken`.
#  *  <br />
#  *  **Note:** This property is not sent over the WebSocket and is exclusive to the idex-sdk.
#  */
# export type AuthTokenWebSocketRequestBalancesSubscription = Expand<
#   WebSocketRequestBalancesSubscription & WebSocketRequestWallet
# >;
#
# /**
#  * @typedef {Object} AuthTokenWebSocketRequestOrdersSubscription
#  * @property {'orders'} name - The name of the subscription
#  * @property {string} wallet -
#  *  Orders subscription with `wallet` attribute, which is fed to the `websocketAuthTokenFetch`
#  *  function when needed to get an updated `wsToken`.
#  *  <br />
#  *  **Note:** This property is not sent over the WebSocket and is exclusive to the idex-sdk.
#  */
# export type AuthTokenWebSocketRequestOrdersSubscription = Expand<
#   WebSocketRequestOrdersSubscription & WebSocketRequestWallet
# >;
#
# /**
#  * @typedef {(WebSocketRequestBalancesSubscription|WebSocketRequestOrdersSubscription)} WebSocketRequestAuthenticatedSubscription
#  */
# export type WebSocketRequestAuthenticatedSubscription =
#   | WebSocketRequestBalancesSubscription
#   | WebSocketRequestOrdersSubscription;
#
# /**
#  * @typedef {(WebSocketRequestCandlesSubscription|WebSocketRequestL1OrderBookSubscription|WebSocketRequestL2OrderBookSubscription|WebSocketRequestTickersSubscription|WebSocketRequestTradesSubscription)} WebSocketRequestUnauthenticatedSubscription
#  */
# export type WebSocketRequestUnauthenticatedSubscription =
#   | WebSocketRequestCandlesSubscription
#   | WebSocketRequestL1OrderBookSubscription
#   | WebSocketRequestL2OrderBookSubscription
#   | WebSocketRequestTickersSubscription
#   | WebSocketRequestTradesSubscription;
#
# /**
#  * @typedef {(AuthTokenWebSocketRequestBalancesSubscription|AuthTokenWebSocketRequestOrdersSubscription)} AuthTokenWebSocketRequestAuthenticatedSubscription
#  */
# export type AuthTokenWebSocketRequestAuthenticatedSubscription =
#   | AuthTokenWebSocketRequestBalancesSubscription
#   | AuthTokenWebSocketRequestOrdersSubscription;
#
# /**
#  * @typedef {(AuthTokenWebSocketRequestAuthenticatedSubscription|}WebSocketRequestUnauthenticatedSubscription) AuthTokenWebSocketRequestAuthenticatedSubscription
#  */
# export type AuthTokenWebSocketRequestSubscription =
#   | AuthTokenWebSocketRequestAuthenticatedSubscription
#   | WebSocketRequestUnauthenticatedSubscription;
#
# /**
#  * @typedef {(AuthTokenWebSocketRequestAuthenticatedSubscription|WebSocketRequestUnauthenticatedSubscription)} WebSocketRequestSubscription
#  */
# export type WebSocketRequestSubscription =
#   | AuthTokenWebSocketRequestAuthenticatedSubscription
#   | WebSocketRequestUnauthenticatedSubscription;
#
# /**
#  * @typedef {Object} WebSocketRequestSubscriptionsByName
#  * @property {WebSocketRequestSubscriptionsByName} balances
#  * @property {WebSocketRequestOrdersSubscription} orders
#  * @property {WebSocketRequestCandlesSubscription} candles
#  * @property {WebSocketRequestL1OrderBookSubscription} l1orderbook
#  * @property {WebSocketRequestL2OrderBookSubscription} l2orderbook
#  * @property {WebSocketRequestTickersSubscription} tickers
#  * @property {WebSocketRequestTradesSubscription} trades
#  */
# export type WebSocketRequestSubscriptionsByName = {
#   balances: WebSocketRequestBalancesSubscription;
#   orders: WebSocketRequestOrdersSubscription;
#   candles: WebSocketRequestCandlesSubscription;
#   l1orderbook: WebSocketRequestL1OrderBookSubscription;
#   l2orderbook: WebSocketRequestL2OrderBookSubscription;
#   tickers: WebSocketRequestTickersSubscription;
#   trades: WebSocketRequestTradesSubscription;
# };
#
# export type WebSocketRequestSubscribeShortNames = Exclude<
#   keyof WebSocketRequestSubscriptionsByName,
#   'candles'
# >;
#
# export type WebSocketRequestUnsubscribeShortNames = keyof WebSocketRequestSubscriptionsByName;
#
# export type WebSocketRequestSubscribeStrictWithTopLevelMarkets = {
#   method: 'subscribe';
#   cid?: string;
#   token?: string;
#   markets: string[];
#   // when markets is provided, we can accept string subscriptions or full subscriptions
#   // and the subscriptions markets parameter is optional.  Candles can never be specified
#   // by name only due to requiring the `interval` property
#   subscriptions: (
#     | WebSocketRequestAuthenticatedSubscription['name']
#     | Exclude<WebSocketRequestUnauthenticatedSubscription['name'], 'candles'>
#     | AugmentedOptional<WebSocketRequestUnauthenticatedSubscription, 'markets'>
#     | WebSocketRequestAuthenticatedSubscription
#   )[];
# };
#
# export type WebSocketRequestSubscribeStrictWithoutTopLevelMarkets = {
#   method: 'subscribe';
#   cid?: string;
#   token?: string;
#   markets?: undefined;
#   // when top level markets property is not provided, authenticated subscriptions may still be defined
#   // by name but all unauthenticated subscriptions require the markets array so may not be defined only
#   // by their name.
#   subscriptions: (
#     | WebSocketRequestUnauthenticatedSubscription
#     | WebSocketRequestAuthenticatedSubscription
#     | WebSocketRequestAuthenticatedSubscription['name']
#   )[];
# };
#
# // This type is strictly typed and understands how subscriptions should look
# // depending on if a top level markets array is provided.
# export type WebSocketRequestSubscribeStrict =
#   | WebSocketRequestSubscribeStrictWithTopLevelMarkets
#   | WebSocketRequestSubscribeStrictWithoutTopLevelMarkets;
#
# // less strict subscribe shape
# export type WebSocketRequestSubscribe = {
#   method: 'subscribe';
#   cid?: string;
#   token?: string;
#   markets?: string[];
#   subscriptions: Array<
#     | WebSocketRequestUnauthenticatedSubscription
#     | WebSocketRequestAuthenticatedSubscription
#     | WebSocketRequestUnauthenticatedSubscription['name']
#   >;
# };
#
# // Loose typing to use while parsing or building
# export type WebSocketRequestSubscriptionLoose = {
#   name: string;
#   markets?: string[];
#   interval?: keyof typeof enums.CandleInterval;
# };
#
# // Subscription Objects in unsubscribe must have name but all other properties are
# // considered optional
# export type WebSocketRequestUnsubscribeSubscription = AugmentedRequired<
#   Partial<
#     | WebSocketRequestUnauthenticatedSubscription
#     | WebSocketRequestAuthenticatedSubscription
#   >,
#   'name'
# >;
#
# /**
#  * UnsubscribeRequest
#  *
#  * @typedef {Object} WebSocketRequestUnsubscribe
#  * @property {string} method - 'unsubscribe'
#  * @property {string} [cid] - client-supplied request id
#  * @property {string[]} [markets] - array of market symbols
#  * @property {(WebSocketRequestUnsubscribeSubscription | WebSocketRequestUnsubscribeShortNames)[]} [subscriptions] - array of subscription objects
#  */
# export type WebSocketRequestUnsubscribe = {
#   method: 'unsubscribe';
#   cid?: string;
#   markets?: string[];
#   subscriptions?: (
#     | WebSocketRequestUnsubscribeSubscription
#     | WebSocketRequestUnsubscribeShortNames
#   )[];
# };
#
# /**
#  * SubscriptionsRequest
#  *
#  * @typedef {Object} WebSocketRequestSubscriptions
#  * @property {string} method - 'subscriptions'
#  * @property {string} [cid] - customer-supplied request id
#  */
# export type WebSocketRequestSubscriptions = {
#   method: 'subscriptions';
#   cid?: string;
# };
#
# """
