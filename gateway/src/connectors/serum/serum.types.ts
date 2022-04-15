import { PublicKey } from '@solana/web3.js';
import {
  Market as SerumMarket,
  Orderbook as SerumOrderBook,
} from '@project-serum/serum';
import {
  Order as SerumOrder,
  OrderParams,
  OrderParams as SerumOrderParams,
} from '@project-serum/serum/lib/market';

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

export interface Market {
  name: string;
  address: PublicKey;
  programId: PublicKey;
  deprecated: boolean;
  minimumOrderSize: number;
  tickSize: number;
  minimumBaseIncrement?: number;
  market: SerumMarket;
}

export interface OrderBook {
  market: Market;
  bids: Map<string, Order>;
  asks: Map<string, Order>;
  orderBook: {
    asks: SerumOrderBook;
    bids: SerumOrderBook;
  };
}

export interface Order extends OrderParams {
  id: string; // client-side id
  exchangeId: string;
  marketName: string;
  ownerAddress: string;
  price: number;
  amount: number;
  sideEnum: OrderSide; // TODO check how to handle collision!!!
  status: OrderStatus;
  orderType: any; // TODO check how to properly use: orderType?: 'limit' | 'ioc' | 'postOnly';!!!
  postOnly: boolean; // TODO is this needed? check how to properly use: orderType?: 'limit' | 'ioc' | 'postOnly';!!!
  fees: Fee;
  filledTimestamp: number;
  order: SerumOrder;
}

export interface Ticker {
  price: number;
  amount: number;
  side: OrderSide;
  timestamp: number;
  ticker: any;
}

export interface Fee {
  maker: number;
  taker: number;
}

//
// Requests subtypes
//

export type GetMarketsRequest = { name: string } | { names: string[] };

export type GetOrderBooksRequest =
  | { marketName: string }
  | { marketNames: string[] };

export type GetTickersRequest =
  | { marketName: string }
  | { marketNames: string[] };

export interface GetOrderRequest {
  marketName: string; // TODO is this necessary?!!!
  ownerAddress: string; // TODO is this necessary?!!!
  clientId?: string;
  exchangeId?: string;
}

// TODO The OrderSide is using uppercase but the SerumOrderParams use a union type, check!!!
export interface CreateOrderRequest extends SerumOrderParams {
  marketName: string;
  ownerAddress: string;
}

export interface CancelOrderRequest {
  marketName?: string;
  clientId?: string;
  exchangeId?: string;
  ownerAddress: string;
}

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

export interface CancelOpenOrderRequest {
  marketName?: string;
  clientId?: string;
  exchangeId?: string;
  ownerAddress: string;
}

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

//
//  Errors
//

export class SerumishError extends Error {}

export class MarketNotFoundError extends SerumishError {}

export class OrderNotFoundError extends SerumishError {}
