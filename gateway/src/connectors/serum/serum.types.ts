import {
  Market as SMarket,
  Orderbook as SOrderBook,
} from '@project-serum/serum';
import {
  MarketOptions as SMarketOptions,
  OpenOrders as SOpenOrders,
  Order as SOrder,
  OrderParams as SOrderParams,
} from '@project-serum/serum/lib/market';
import { PublicKey, TransactionSignature } from '@solana/web3.js';
import BN from 'bn.js';
import { Map as ImmutableMap, Set as ImmutableSet } from 'immutable';
import { Market as ExtendedMarket } from './extensions/market';

// export type FunctionType<Arguments, Return> = (...args: Arguments[]) => Return;

// export type AsyncFunctionType<Arguments, Return> = (
//   ...args: Arguments[]
// ) => Promise<Return>;

export type IMap<K, V> = ImmutableMap<K, V>;
export const IMap = ImmutableMap;
export type ISet<V> = ImmutableSet<V>;
export const ISet = ImmutableSet;

export type SerumOrder = SOrder;
export type SerumMarket = ExtendedMarket;
export const SerumMarket = ExtendedMarket;
export type SerumOrderBook = SOrderBook;
export const SerumOrderBook = SOrderBook;
export type SerumOrderParams<T> = SOrderParams<T>;
export type SerumMarketOptions = SMarketOptions;
export type SerumOpenOrders = SOpenOrders;
export const SerumOpenOrders = SOpenOrders;

export type OriginalSerumMarket = SMarket;

interface PlainBasicSerumMarket {
  address: string;
  deprecated: boolean;
  name: string;
  programId: string;
}

interface FatBasicSerumMarket {
  address: PublicKey;
  name: string;
  programId: PublicKey;
  deprecated: boolean;
}

export type BasicSerumMarket = PlainBasicSerumMarket | FatBasicSerumMarket;

export enum OrderSide {
  BUY = 'BUY',
  SELL = 'SELL',
}

export enum OrderStatus {
  OPEN = 'OPEN',
  CANCELED = 'CANCELED',
  FILLED = 'FILLED',
  CREATION_PENDING = 'CREATION_PENDING',
  CANCELATION_PENDING = 'CANCELATION_PENDING',
  UNKNOWN = 'UNKNOWN',
}

export enum OrderType {
  LIMIT = 'LIMIT',
  IOC = 'IOC', // Immediate or Cancel
  POST_ONLY = 'POST_ONLY',
}

export enum TickerSource {
  NOMIMCS = 'nomics',
  ALEPH = 'aleph',
}

export interface Market {
  name: string;
  address: PublicKey;
  programId: PublicKey;
  deprecated: boolean;
  minimumOrderSize: number;
  tickSize: number;
  minimumBaseIncrement?: BN;
  fees: Fee;
  market: SerumMarket;
}

export interface OrderBook {
  market: Market;
  bids: IMap<string, Order>;
  asks: IMap<string, Order>;
  orderBook: {
    asks: SerumOrderBook;
    bids: SerumOrderBook;
  };
}

export interface Ticker {
  price: number;
  timestamp: number;
  ticker: any;
}

export interface Order {
  id?: string; // client id
  exchangeId?: string;
  marketName: string;
  ownerAddress?: string;
  price: number;
  amount: number;
  side: OrderSide;
  status?: OrderStatus;
  type?: OrderType;
  fillmentTimestamp?: number;
  signature?: string;
  order?: SerumOrder;
}

export type Fund = TransactionSignature;

export interface Fee {
  maker: number;
  taker: number;
}

//
// Requests subtypes
//

export type GetMarketsRequest =
  | Record<string, never>
  | { name: string }
  | { names: string[] };

export interface GetMarketResponse {
  name: string;
  address: PublicKey;
  programId: PublicKey;
  deprecated: boolean;
  minimumOrderSize: number;
  tickSize: number;
  minimumBaseIncrement?: string;
  fees: Fee;
}

export type GetMarketsResponse =
  | IMap<string, GetMarketResponse>
  | GetMarketResponse;

export type GetOrderBooksRequest =
  | Record<string, never>
  | { marketName: string }
  | { marketNames: string[] };

export interface GetOrderBookResponse {
  market: GetMarketResponse;
  bids: Map<string, GetOrderResponse>;
  asks: Map<string, GetOrderResponse>;
}

export type GetOrderBooksResponse =
  | IMap<string, GetOrderBookResponse>
  | GetOrderBookResponse;

export type GetTickersRequest =
  | Record<string, never>
  | { marketName: string }
  | { marketNames: string[] };

export interface GetTickerResponse {
  price: number;
  timestamp: number;
}

export type GetTickersResponse =
  | IMap<string, GetTickerResponse>
  | GetTickerResponse;

export interface GetOrderRequest {
  id?: string;
  exchangeId?: string;
  marketName?: string;
  ownerAddress: string;
}

export interface GetOrdersRequest {
  ids?: string[];
  exchangeIds?: string[];
  marketName?: string;
  ownerAddress: string;
}

export interface GetOrderResponse {
  id?: string;
  exchangeId?: string;
  marketName: string;
  ownerAddress?: string;
  price: number;
  amount: number;
  side: OrderSide;
  status?: OrderStatus;
  type?: OrderType;
  fee?: number;
  fillmentTimestamp?: number;
}

export type GetOrdersResponse =
  | IMap<string, IMap<string, GetOrderResponse>>
  | IMap<string, GetOrderResponse>
  | GetOrderResponse;

export interface CreateOrdersRequest {
  id?: string;
  marketName: string;
  ownerAddress: string;
  payerAddress?: string;
  side: OrderSide;
  price: number;
  amount: number;
  type?: OrderType;
}

export interface CreateOrderResponse {
  id?: string;
  exchangeId?: string;
  marketName: string;
  ownerAddress?: string;
  price: number;
  amount: number;
  side: OrderSide;
  status?: OrderStatus;
  type?: OrderType;
  fee?: number;
  signature?: string;
}

export type CreateOrdersResponse =
  | IMap<string, CreateOrderResponse>
  | CreateOrderResponse;

export interface CancelOrderRequest {
  id?: string;
  exchangeId?: string;
  marketName: string;
  ownerAddress: string;
}

export interface CancelOrdersRequest {
  ids?: string[];
  exchangeIds?: string[];
  marketName: string;
  ownerAddress: string;
}

export interface CancelOrderResponse {
  id?: string;
  exchangeId?: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  side: OrderSide;
  status?: OrderStatus;
  type?: OrderType;
  fee?: number;
  signature?: string;
}

export type CancelOrdersResponse =
  | IMap<string, CancelOrderResponse>
  | CancelOrderResponse;

export interface GetOpenOrderRequest {
  id?: string;
  exchangeId?: string;
  marketName?: string;
  ownerAddress: string;
}

export interface GetOpenOrdersRequest {
  ids?: string[];
  exchangeIds?: string[];
  marketName?: string;
  ownerAddress: string;
}

export interface GetOpenOrderResponse {
  id?: string;
  exchangeId?: string;
  marketName: string;
  ownerAddress?: string;
  price: number;
  amount: number;
  side: OrderSide;
  status?: OrderStatus;
  type?: OrderType;
  fee?: number;
}

export type GetOpenOrdersResponse =
  | IMap<string, IMap<string, GetOpenOrderResponse>>
  | IMap<string, GetOpenOrderResponse>
  | GetOpenOrderResponse;

export interface GetFilledOrderRequest {
  id?: string;
  exchangeId?: string;
  marketName?: string;
  ownerAddress: string;
}

export interface GetFilledOrdersRequest {
  ids?: string[];
  exchangeIds?: string[];
  marketName?: string;
  ownerAddress?: string;
}

export interface GetFilledOrderResponse {
  id?: string;
  exchangeId?: string;
  marketName: string;
  ownerAddress?: string;
  price: number;
  amount: number;
  side: OrderSide;
  status?: OrderStatus;
  type?: OrderType;
  fee?: number;
  fillmentTimestamp?: number;
}

export type GetFilledOrdersResponse =
  | IMap<string, IMap<string, GetFilledOrderResponse>>
  | IMap<string, GetFilledOrderResponse>
  | GetFilledOrderResponse;

export type SettleFundsRequest =
  | { ownerAddress: string }
  | { marketName: string; ownerAddress: string }
  | { marketNames: string[]; ownerAddress: string };

export type PostSettleFundResponse = Fund[];

export type SettleFundsResponse =
  | IMap<string, PostSettleFundResponse>
  | PostSettleFundResponse;

//
//  Errors
//

export class SerumishError extends Error {}

export class MarketNotFoundError extends SerumishError {}

export class TickerNotFoundError extends SerumishError {}

export class OrderNotFoundError extends SerumishError {}

export class FundsSettlementError extends SerumishError {}
