import {Account, PublicKey} from '@solana/web3.js';
import {Market as SerumMarket, Orderbook as SerumOrderBook,} from '@project-serum/serum';
import {Order as SerumOrder, OrderParams as SerumOrderParams,} from '@project-serum/serum/lib/market';
import {Map as ImmutableMap} from 'immutable';
import BN from "bn.js";

export enum OrderSide {
  BUY = 'BUY',
  SELL = 'SELL',
}

export type OrderStatus =
  | 'OPEN'
  | 'PENDING'
  | 'FILLED'
  | 'CANCELED'
  | 'FAILED'
  | 'EXPIRED'
  | 'TIMED_OUT'
  | 'UNKNOWN';

export type OrderType = 'LIMIT' | 'IOC' | 'POST_ONLY';

export interface Market {
  name: string;
  address: PublicKey;
  programId: PublicKey;
  deprecated: boolean;
  minimumOrderSize: number;
  tickSize: number;
  minimumBaseIncrement?: number;
  fees: Fee;
  market: SerumMarket;
}

export interface OrderBook {
  market: Market;
  bids: ImmutableMap<string, Order>;
  asks: ImmutableMap<string, Order>;
  orderBook: {
    asks: SerumOrderBook;
    bids: SerumOrderBook;
  };
}

export interface Ticker {
  price: number;
  amount: number;
  side: OrderSide;
  timestamp: number;
  ticker: any;
}

export interface Order {
  id: string; // client-side id
  exchangeId: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  side: OrderSide; // TODO check how to handle collision!!!
  status: OrderStatus;
  orderType: OrderType; // // TODO create enum, check how to handle collision!!!
  fee: number; // TODO  fee: string; // can be positive, when paying, or negative, when rebated probably remove, show how much fees were paid for the order!!!
  fillmentTimestamp: number;
  order: SerumOrder;

  owner: Account;
  payer: PublicKey;
  size: number;
  clientId?: BN;
  openOrdersAddressKey?: PublicKey;
  openOrdersAccount?: Account;
  feeDiscountPubkey?: PublicKey | null;
  selfTradeBehavior?: 'decrementTake' | 'cancelProvide' | 'abortTransaction' | undefined;
  programId?: PublicKey;
}

export interface Fee {
  maker: number;
  taker: number;
}

//
// Requests subtypes
//

export type GetMarketsRequest = { name: string } | { names: string[] };

export interface GetMarketResponse {
  name: string;
  address: PublicKey;
  programId: PublicKey;
  deprecated: boolean;
  minimumOrderSize: number;
  tickSize: number;
  minimumBaseIncrement?: number;
  fees: Fee;
}

export type GetMarketsResponse = ImmutableMap<string, GetMarketResponse> | GetMarketResponse;

export type GetOrderBooksRequest =
  | { marketName: string }
  | { marketNames: string[] };

export interface GetOrderBookResponse {
  market: GetMarketResponse;
  bids: ImmutableMap<string, GetOrderResponse>;
  asks: ImmutableMap<string, GetOrderResponse>;
}
export type GetOrderBooksResponse = ImmutableMap<string, GetOrderBookResponse> | GetOrderBookResponse;

export type GetTickersRequest =
  | { marketName: string }
  | { marketNames: string[] };

export interface GetTickerResponse {
  price: number;
  amount: number;
  side: OrderSide;
  timestamp: number;
}

export type GetTickersResponse = ImmutableMap<string, GetTickerResponse> | GetTickerResponse;

export interface GetOrdersRequest {
  marketName?: string;
  clientId?: string;
  exchangeId?: string;
  ownerAddress: string;
}

export interface GetOrderResponse {
  id: string;
  exchangeId: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  side: OrderSide;
  status: OrderStatus;
  orderType: OrderType;
  fee: number;
  fillmentTimestamp: number;
}

export type GetOrdersResponse = ImmutableMap<string, GetOrderResponse> | GetOrderResponse;

// TODO The OrderSide is using uppercase but the SerumOrderParams use a union type, check!!!
export interface CreateOrdersRequest extends SerumOrderParams {
  marketName: string;
  ownerAddress: string;
}

export interface CreateOrderResponse {
  id: string;
  exchangeId: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  side: OrderSide;
  status: OrderStatus;
  orderType: OrderType;
  fee: number
}

export type CreateOrdersResponse = ImmutableMap<string, CreateOrderResponse> | CreateOrderResponse;

export interface CancelOrdersRequest {
  marketName?: string;
  clientId?: string;
  exchangeId?: string;
  ownerAddress: string;
}

export interface CancelOrderResponse {
  id: string;
  exchangeId: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  side: OrderSide;
  status: OrderStatus;
  orderType: OrderType;
  fee: number
}

export type CancelOrdersResponse = ImmutableMap<string, CancelOrderResponse> | CancelOrderResponse;

export interface GetOpenOrderRequest {
  marketName?: string;
  clientId?: string;
  exchangeId?: string;
  ownerAddress: string;
}

export interface GetOpenOrdersRequest {
  marketName?: string;
  clientIds?: string[];
  exchangeIds?: string[];
  ownerAddress: string;
}

export interface GetOpenOrderResponse {
  id: string;
  exchangeId: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  side: OrderSide;
  status: OrderStatus;
  orderType: OrderType;
  fee: number
}

export type GetOpenOrdersResponse = ImmutableMap<string, GetOpenOrderResponse> | GetOpenOrderResponse;

export interface CancelOpenOrdersRequest {
  marketName?: string;
  clientId?: string;
  exchangeId?: string;
  ownerAddress: string;
}

export interface CancelOpenOrderResponse {
  id: string;
  exchangeId: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  side: OrderSide;
  status: OrderStatus;
  orderType: OrderType;
  fee: number
}

export type CancelOpenOrdersResponse = ImmutableMap<string, CancelOpenOrderResponse> | CancelOpenOrderResponse;

export interface GetFilledOrderRequest {
  marketName?: string;
  clientId?: string;
  exchangeId?: string;
  ownerAddress: string;
}

export interface GetFilledOrdersRequest {
  marketName?: string;
  clientIds?: string[];
  exchangeIds?: string[];
  ownerAddress?: string;
}

export interface GetFilledOrderResponse {
  id: string;
  exchangeId: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  side: OrderSide;
  status: OrderStatus;
  orderType: OrderType;
  fee: number;
  fillmentTimestamp: number;
}

export type GetFilledOrdersResponse = ImmutableMap<string, GetFilledOrderResponse> | GetFilledOrderResponse;

//
//  Errors
//

export class SerumishError extends Error {}

export class MarketNotFoundError extends SerumishError {}

export class OrderNotFoundError extends SerumishError {}
