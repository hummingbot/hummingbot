import { NetworkSelectionRequest } from '../../services/common-interfaces';
import {
  CancelOpenOrderRequest,
  CancelOrderRequest,
  CreateOrderRequest,
  GetFilledOrderRequest, GetFilledOrdersRequest,
  GetMarketsRequest,
  GetOpenOrderRequest, GetOpenOrdersRequest,
  GetOrderBooksRequest,
  GetOrderRequest,
  GetTickersRequest,
  Market,
  Order,
  OrderBook,
  Ticker,
} from './serum.types';

//
// GET /clob/markets
//

export type SerumGetMarketsRequest = NetworkSelectionRequest &
  GetMarketsRequest;

export type SerumGetMarketsResponse = Map<string, Market> | Market;

//
// GET /clob/orderBooks
//

export type SerumGetOrderBooksRequest = NetworkSelectionRequest &
  GetOrderBooksRequest;

export type SerumGetOrderBooksResponse = Map<string, OrderBook> | OrderBook;

//
// GET /clob/tickers
//

export type SerumGetTickersRequest = NetworkSelectionRequest &
  GetTickersRequest;

export type SerumGetTickersResponse = Map<string, Ticker> | Ticker;

//
// GET /clob/orders
//

export type SerumGetOrdersRequest = NetworkSelectionRequest &
  (
    | { order: GetOrderRequest }
    | {
        orders: GetOrderRequest[];
      }
  );

export type SerumGetOrdersResponse = Map<string, Order> | Order;

//
// POST /clob/orders
//

export type SerumCreateOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CreateOrderRequest }
    | {
        orders: CreateOrderRequest[];
      }
  );

export type SerumCreateOrdersResponse = Map<string, Order> | Order;

//
// DELETE /clob/orders
//

export type SerumCancelOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CancelOrderRequest }
    | {
        orders: CancelOrderRequest[];
      }
  );

export type SerumCancelOrdersResponse = Map<string, Order> | Order;

//
// GET /clob/openOrders
//

export type SerumGetOpenOrdersRequest = NetworkSelectionRequest &
  (
    | { order: GetOpenOrderRequest }
    | {
        orders: GetOpenOrdersRequest[];
      }
  );

export type SerumGetOpenOrdersResponse = Map<string, Order> | Order;

//
// DELETE /clob/openOrders
//

export type SerumCancelOpenOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CancelOpenOrderRequest }
    | {
        orders: CancelOpenOrderRequest[];
      }
  );

export type SerumCancelOpenOrdersResponse = Map<string, Order> | Order;

//
// GET /clob/filledOrders
//

export type SerumGetFilledOrdersRequest = NetworkSelectionRequest &
  (
    | { order: GetFilledOrderRequest }
    | {
        orders: GetFilledOrdersRequest[];
      }
  );

export type SerumGetFilledOrdersResponse = Map<string, Order> | Order;
