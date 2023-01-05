import { Map as ImmutableMap, Set as ImmutableSet } from 'immutable';
import { BookOffer } from 'xrpl';

export type IMap<K, V> = ImmutableMap<K, V>;
export const IMap = ImmutableMap;
export type ISet<V> = ImmutableSet<V>;
export const ISet = ImmutableSet;

export enum OrderSide {
  BUY = 'BUY',
  SELL = 'SELL',
}

export enum OrderStatus {
  OPEN = 'OPEN',
  CANCELED = 'CANCELED',
  FILLED = 'FILLED',
  PARTIALLY_FILLED = 'PARTIALLY_FILLED',
  PENDING = 'PENDING',
  FAILED = 'FAILED',
  UNKNOWN = 'UNKNOWN',
}

export enum OrderType {
  LIMIT = 'LIMIT',
  PASSIVE = 'PASSIVE',
  IOC = 'IOC', // Immediate or Cancel
  FOK = 'FOK', // Fill or Kill
  SELL = 'SELL', // Sell
}

export interface Token {
  currency: string;
  issuer: string;
  value: string;
}

export type GetMarketsRequest =
  | Record<string, never>
  | { name: string }
  | { names: string[] };

export interface GetMarketResponse {
  name: string;
  minimumOrderSize: number;
  tickSize: number;
  baseTransferRate: number;
  quoteTransferRate: number;
}

export interface Market {
  name: string;
  minimumOrderSize: number;
  tickSize: number;
  baseTransferRate: number;
  quoteTransferRate: number;
}

export type GetMarketsResponse =
  | IMap<string, GetMarketResponse>
  | GetMarketResponse;

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

export interface Ticker {
  price: number;
  timestamp: number;
}

export interface GetOrderRequest {
  sequence: number;
  signature: string;
}

export type GetOrdersRequest =
  | Record<string, never>
  | { orders: GetOrderRequest[] };

export interface GetOrderResponse {
  sequence: number;
  status: OrderStatus;
  signature: string;
  transactionResult: string;
}

export type GetOrdersResponse = Record<number, GetOrderResponse>;

export type GetOrderBooksRequest =
  | Record<string, never>
  | { marketName: string; limit: number }
  | { marketNames: string[]; limit: number };

export interface GetOrderBookResponse {
  market: GetMarketResponse;
  topAsk: number;
  topBid: number;
  midPrice: number;
  bids: BookOffer[];
  asks: BookOffer[];
  timestamp: number;
}

export type GetOrderBooksResponse =
  | IMap<string, GetOrderBookResponse>
  | GetOrderBookResponse;

export interface CreateOrderRequest {
  walletAddress: string;
  marketName: string;
  side: OrderSide;
  price: number;
  amount: number;
  type?: OrderType;
  sequence?: number;
}

export interface CreateOrderResponse {
  walletAddress: string;
  marketName: string;
  price: number;
  amount: number;
  side: OrderSide;
  status?: OrderStatus;
  type?: OrderType;
  fee?: number;
  sequence: number;
  orderLedgerIndex?: string;
  signature?: string;
  transactionResult?: string;
}

export type CreateOrdersResponse =
  | IMap<number, CreateOrderResponse>
  | CreateOrderResponse
  | Record<number, CreateOrderResponse>;

export interface CancelOrderRequest {
  walletAddress: string;
  offerSequence: number;
}

export type CancelOrdersRequest =
  | Record<string, never>
  | { order: CancelOrderRequest }
  | { orders: CancelOrderRequest[] };

export interface CancelOrderResponse {
  walletAddress: string;
  status?: OrderStatus;
  signature?: string;
  transactionResult?: string;
}

export type CancelOrdersResponse =
  | IMap<number, CancelOrderResponse>
  | CancelOrderResponse
  | Record<number, CancelOrderResponse>;

export interface GetOpenOrderRequest {
  marketName: string;
  walletAddress: string;
}

export interface GetOpenOrderResponse {
  sequence: number;
  marketName: string;
  price: string;
  amount: string;
  side: OrderSide;
}

export type GetOpenOrdersResponse =
  | any
  | IMap<string, IMap<number, GetOpenOrderResponse>>
  | IMap<number, GetOpenOrderResponse>
  | GetOpenOrderResponse;

export class XRPLDEXishError extends Error {}

export class MarketNotFoundError extends XRPLDEXishError {}
