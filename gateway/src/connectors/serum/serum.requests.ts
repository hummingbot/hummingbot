import {
  NetworkSelectionRequest,
  BaseResponse,
} from '../services/common-interfaces';

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

export type SerumGetMarketsRequest = NetworkSelectionRequest &
  (
    | { name: string }
    | {
        names: string[];
      }
  );

export class SerumGetMarketsResponse extends BaseResponse<
  Market[] | Market | null
> {}

//
// GET /clob/orderBooks
//

export interface SerumGetOrderBooksRequest extends NetworkSelectionRequest {
  marketNames: string[]; // TODO marketName instead of seperated quote & base (in line with self._trading_pairs)!!!
  depth?: number; // TODO is this needed?!!!
}

export interface SerumGetOrderBooksResponse {
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

export interface SerumGetTickersRequest extends NetworkSelectionRequest {
  marketNames?: [];
}

export interface SerumGetTickersResponse {
  lastTradedPrices: Ticker[];
}

//
// Orders
//

export interface SerumOrdersResponse {
  status: OrderStatus;
  exchangeOrderId?: string;
  clientOrderId?: string;
}

//
// GET /clob/orders
//

export interface SerumGetOrdersRequestItem {
  marketName?: string;
  clientOrderId?: string;
  exchangeOrderId?: string;
}

export interface SerumGetOrdersRequest extends NetworkSelectionRequest {
  orders: SerumGetOrdersRequestItem[];
}

export interface SerumGetOrdersResponseItem {
  // TODO fill interface with the correct fields!!!
}

export interface SerumGetOrdersResponse extends SerumOrdersResponse {
  // TODO check what orderWithFills means!!! Ask Mike
  orders: SerumGetOrdersResponseItem[];
}

//
// POST /clob/orders
//

export interface SerumPostOrdersRequest extends NetworkSelectionRequest {
  address: string;
  marketName: string;
  side: OrderSide;
  amount: string;
  price: string;
  orderType: 'LIMIT' | 'MARKET'; // market == ioc (immediate-or-cancel)
  postOnly: boolean; // place only an order, if no liquidity has been taken
  clientOrderId?: string; // set a client's own orderId for tracking
}

export interface SerumPostOrdersResponse extends SerumOrdersResponse {
}

//
// DELETE /clob/orders
//

export interface SerumDeleteOrdersRequest extends NetworkSelectionRequest {
  address: string; // solana account, which orders belong to
  exchangeOrderId?: string; // is simply 'orderId' in mango.ts
  clientOrderId?: string;
}

export interface SerumDeleteOrdersResponse extends SerumOrdersResponse {
}

//
// GET /clob/openOrders
//

export interface SerumGetOpenOrdersRequest extends NetworkSelectionRequest {
  address?: string; // filter by owner
  marketName?: string; // filter by market (can speed up request dramatically)
  exchangeOrderId?: string; // filter by exchangeOrderId
  clientOrderId?: string; // filter by clientOrderId
}

export interface SerumGetOpenOrdersResponse {
  spot: OpenClientOrder[];
  perp: OpenClientOrder[];
}

//
// DELETE /clob/openOrders
//

export interface SerumDeleteOpenOrdersRequest extends NetworkSelectionRequest {
  address: string; // solana account, for which to cancel
  marketNames?: string[]; // on which markets to cancel
}

export interface SerumDeleteOpenOrdersResponse {
  orders: SerumOrdersResponse;
}

//
// GET /clob/filledOrders
//

export interface SerumGetFilledOrdersRequest extends NetworkSelectionRequest {
  marketNames?: string[];
  account?: string;
}

export interface SerumGetFilledOrdersResponse {
  // sorted from newest to oldest
  spot: FilledOrder[];
  perp: FilledOrder[];
}
