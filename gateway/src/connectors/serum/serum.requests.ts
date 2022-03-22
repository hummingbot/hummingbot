import {
  FilledOrder,
  OpenClientOrder,
  SimpleOrderBook,
  MarketInfo,
} from './serum.types';

//
// GET /markets
//

export interface SerumMarketsRequest {
  // TODO: It could be that address is needed for fee rebates
  marketNames?: string[]; // returns all markets, if none
}

export interface SerumMarketsResponse {
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

export interface SerumTickerResponse {
  lastTradedPrices: TickerItem[];
}

//
// GET /orderbook
//
export interface SerumOrderbookRequest {
  marketNames: string[];
  depth?: number;
}

export interface SerumOrderbookResponse {
  orderBooks: SimpleOrderBook[];
}

//
// GET /order
//
export interface SerumGetOrderRequest {
  marketName?: string;
  clientOrderId?: string;
  exchangeOrderId?: string;
}

//
// POST /order
//
export interface SerumPostOrderRequest {
  address: string;
  marketName: string;
  side: 'BUY' | 'SELL';
  amount: string;
  price: string;
  order_type: 'LIMIT' | 'MARKET'; // market == ioc (immediate-or-cancel)
  postOnly: boolean; // place only an order, if no liquidity has been taken
  clientOrderId?: string; // set a client's own orderId for tracking
}

export interface SerumOrderResponse {
  status: 'OPEN' | 'FILLED' | 'CANCELED' | 'UNKNOWN' | 'FAILED' | 'DONE';
  exchangeOrderId?: string;
  clientOrderId?: string;
}

//
// Delete /order
//
export interface SerumDeleteOrderRequest {
  address: string; // solana account, which orders belong to
  exchangeOrderId?: string; // is simply 'orderId' in mango.ts
  clientOrderId?: string;
}

//
// GET /openOrders
//
export interface SerumGetOpenOrdersRequest {
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
// DELETE /openOrders
//
export interface SerumDeleteOpenOrdersRequest {
  address: string; // solana account, for which to cancel
  marketNames?: string[]; // on which markets to cancel
}

export interface SerumDeleteOpenOrdersResponse {
  orders: SerumOrderResponse;
}

//
// GET /fills
//
export interface SerumGetFillsRequest {
  marketNames?: string[];
  account?: string;
}

export interface SerumGetFillsResponse {
  // sorted from newest to oldest
  spot: FilledOrder[];
  perp: FilledOrder[];
}
