/* eslint-disable @typescript-eslint/no-empty-interface */
import { NetworkSelectionRequest } from '../services/common-interfaces';

export type Side = 'BUY' | 'SELL';

import {
  FilledOrder,
  OpenClientOrder,
  SimpleOrderBook,
  Market,
} from './clob.types';

//
// GET /clob/markets
//

export interface ClobGetMarketsRequest extends NetworkSelectionRequest {
  // TODO: It could be that address is needed for fee rebates
  marketNames?: string[]; // returns all markets, if none
}

export interface ClobGetMarketsResponse {
  markets: Market[];
}

//
// GET /clob/tickers
//

// TODO remove?!!!
export interface TickerItem {
  marketName: string;
  price: string;
  timestamp: string;
}

export interface ClobGetTickersRequest extends NetworkSelectionRequest {
  // TODO implement!!!
}

export interface ClobGetTickersResponse {
  lastTradedPrices: TickerItem[];
}

//
// GET /clob/orderbooks
//

export interface ClobGetOrderbooksRequest extends NetworkSelectionRequest {
  marketNames: string[]; // TODO marketName instead of seperated quote & base (in line with self._trading_pairs)!!!
  depth?: number;
}

export interface ClobGetOrderbooksResponse {
  orderBooks: SimpleOrderBook[];
}

//
// Orders
//

export interface ClobOrdersResponse {
  status: 'OPEN' | 'FILLED' | 'CANCELED' | 'UNKNOWN' | 'FAILED' | 'DONE';
  exchangeOrderId?: string;
  clientOrderId?: string;
}

//
// GET /clob/orders
//

export interface ClobGetOrdersRequest extends NetworkSelectionRequest {
  marketName?: string;
  clientOrderId?: string;
  exchangeOrderId?: string;
}

export interface ClobGetOrdersResponse extends ClobOrdersResponse {
}

//
// POST /clob/orders
//

export interface ClobPostOrdersRequest extends NetworkSelectionRequest {
  address: string;
  marketName: string;
  side: Side;
  amount: string;
  price: string;
  order_type: 'LIMIT' | 'MARKET'; // market == ioc (immediate-or-cancel)
  postOnly: boolean; // place only an order, if no liquidity has been taken
  clientOrderId?: string; // set a client's own orderId for tracking
}

export interface ClobPostOrdersResponse extends ClobOrdersResponse {
}

//
// DELETE /clob/orders
//

export interface ClobDeleteOrdersRequest extends NetworkSelectionRequest {
  address: string; // solana account, which orders belong to
  exchangeOrderId?: string; // is simply 'orderId' in mango.ts
  clientOrderId?: string;
}

export interface ClobDeleteOrdersResponse extends ClobOrdersResponse {
}

//
// GET /clob/openOrders
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
// DELETE /clob/openOrders
//

export interface ClobDeleteOpenOrdersRequest extends NetworkSelectionRequest {
  address: string; // solana account, for which to cancel
  marketNames?: string[]; // on which markets to cancel
}

export interface ClobDeleteOpenOrdersResponse {
  orders: ClobOrdersResponse;
}

//
// GET /clob/filledOrders
//

export interface ClobGetFilledOrdersRequest extends NetworkSelectionRequest {
  marketNames?: string[];
  account?: string;
}

export interface ClobGetFilledOrdersResponse {
  // sorted from newest to oldest
  spot: FilledOrder[];
  perp: FilledOrder[];
}
