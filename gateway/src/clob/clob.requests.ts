/* eslint-disable @typescript-eslint/no-empty-interface */

import { NetworkSelectionRequest, BaseResponse } from '../services/common-interfaces';

import {
  FilledOrder,
  OpenClientOrder,
  SimpleOrderBook,
  Market,
  OrderSide,
  OrderStatus,
} from './clob.types';

//
// GET /clob/markets
//

export type ClobGetMarketsRequest = NetworkSelectionRequest &
  (
    | { name: string }
    | {
        names: string[];
      }
  );

export class ClobGetMarketsResponse extends BaseResponse<
  Market[] | Market | null
> {}

//
// GET /clob/orderBooks
//

export interface ClobGetOrderBooksRequest extends NetworkSelectionRequest {
  marketNames: string[]; // TODO marketName instead of seperated quote & base (in line with self._trading_pairs)!!!
  depth?: number; // TODO is this needed?!!!
}

export interface ClobGetOrderBooksResponse {
  orderBooks: SimpleOrderBook[];
}

//
// GET /clob/tickers
//

export interface Ticker {
  market: string;
  price: string;
  amount: string;
  side: OrderSide;
  timestamp: string;
}

export interface ClobGetTickersRequest extends NetworkSelectionRequest {
  marketNames?: [];
}

export interface ClobGetTickersResponse {
  lastTradedPrices: Ticker[];
}

//
// Orders
//

export interface ClobOrdersResponse {
  status: OrderStatus;
  exchangeOrderId?: string;
  clientOrderId?: string;
}

//
// GET /clob/orders
//

export interface ClobGetOrdersRequestItem {
  marketName?: string;
  clientOrderId?: string;
  exchangeOrderId?: string;
}

export interface ClobGetOrdersRequest extends NetworkSelectionRequest {
  orders: ClobGetOrdersRequestItem[];
}

export interface ClobGetOrdersResponseItem {
  // TODO fill interface with the correct fields!!!
}

export interface ClobGetOrdersResponse extends ClobOrdersResponse {
  // TODO check what orderWithFills means!!! Ask Mike
  orders: ClobGetOrdersResponseItem[];
}

//
// POST /clob/orders
//

export interface ClobPostOrdersRequest extends NetworkSelectionRequest {
  address: string;
  marketName: string;
  side: OrderSide;
  amount: string;
  price: string;
  orderType: 'LIMIT' | 'MARKET'; // market == ioc (immediate-or-cancel)
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
