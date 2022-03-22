import { NetworkSelectionRequest } from '../services/common-interfaces';

export type Side = 'BUY' | 'SELL';
import {
  FilledOrder,
  OpenClientOrder,
  SimpleOrderBook,
  MarketInfo,
} from './clob.types';

//
// GET /markets
//

export interface ClobMarketsRequest extends NetworkSelectionRequest {
  // TODO: It could be that address is needed for fee rebates
  marketNames?: string[]; // returns all markets, if none
}

export interface ClobMarketsResponse {
  markets: MarketInfo[];
}

//
// GET /ticker
//
export interface TickerItem {
  marketName: string;
  price: string;
  timestamp: string;
}

export interface ClobTickerResponse {
  lastTradedPrices: TickerItem[];
}

//
// GET /orderbook
//
export interface ClobOrderbookRequest extends NetworkSelectionRequest {
  marketNames: string[];
  depth?: number;
}

export interface ClobOrderbookResponse {
  orderBooks: SimpleOrderBook[];
}

//
// GET /order
//
export interface ClobGetOrderRequest extends NetworkSelectionRequest {
  marketName?: string;
  clientOrderId?: string;
  exchangeOrderId?: string;
}

//
// POST /order
//
export interface ClobPostOrderRequest extends NetworkSelectionRequest {
  address: string;
  marketName: string;
  side: Side;
  amount: string;
  price: string;
  order_type: 'LIMIT' | 'MARKET'; // market == ioc (immediate-or-cancel)
  postOnly: boolean; // place only an order, if no liquidity has been taken
  clientOrderId?: string; // set a client's own orderId for tracking
}

export interface ClobOrderResponse {
  status: 'OPEN' | 'FILLED' | 'CANCELED' | 'UNKNOWN' | 'FAILED' | 'DONE';
  exchangeOrderId?: string;
  clientOrderId?: string;
}

//
// Delete /order
//
export interface ClobDeleteOrderRequest extends NetworkSelectionRequest {
  address: string; // solana account, which orders belong to
  exchangeOrderId?: string; // is simply 'orderId' in mango.ts
  clientOrderId?: string;
}

//
// GET /openOrders
//
export interface ClobGetOpenOrdersRequest extends NetworkSelectionRequest {
  address?: string; // filter by owner
  marketName?: string; // filter by market (can speed up request dramatically)
  exchangeOrderId?: string; // filter by exchangeOrderId
  clientOrderId?: string; // filter by clientOrderId
}

export interface ClobGetOpenOrdersResponse {
  spot: OpenClientOrder[];
  perp: OpenClientOrder[];
}

//
// DELETE /openOrders
//
export interface ClobDeleteOpenOrdersRequest extends NetworkSelectionRequest {
  address: string; // solana account, for which to cancel
  marketNames?: string[]; // on which markets to cancel
}

export interface ClobDeleteOpenOrdersResponse {
  orders: ClobOrderResponse;
}

//
// GET /fills
//
export interface ClobGetFillsRequest extends NetworkSelectionRequest {
  marketNames?: string[];
  account?: string;
}

export interface ClobGetFillsResponse {
  // sorted from newest to oldest
  spot: FilledOrder[];
  perp: FilledOrder[];
}
