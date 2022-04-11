import { NetworkSelectionRequest } from '../../services/common-interfaces';
import { CreateOrder, Market, Order, OrderBook, OrderRequest, Ticker } from './serum.types';

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

export type SerumGetMarketsResponse = Map<string, Market> | Market;

//
// GET /clob/orderBooks
//

export type SerumGetOrderBooksRequest = NetworkSelectionRequest &
  (
    | { marketName: string }
    | {
        marketNames: string[];
      }
  );

export type SerumGetOrderBooksResponse = Map<string, OrderBook> | OrderBook;

//
// GET /clob/tickers
//

export type SerumGetTickersRequest = NetworkSelectionRequest &
  (
    | { marketName: string }
    | {
        marketNames: string[];
      }
  );

export type SerumGetTickersResponse = Map<string, Ticker> | Ticker;

//
// GET /clob/orders
//

export type SerumGetOrdersRequest = NetworkSelectionRequest &
  (
    | { order: OrderRequest }
    | {
        orders: OrderRequest[];
      }
  );

export type SerumGetOrdersResponse = Map<string, Order> | Order;

//
// POST /clob/orders
//

export type SerumPostOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CreateOrder }
    | {
        orders: CreateOrder[];
      }
  );

export type SerumPostOrdersResponse = Map<string, Order> | Order;

//
// DELETE /clob/orders
//

export type SerumDeleteOrdersRequest = NetworkSelectionRequest & {};

export type SerumDeleteOrdersResponse = Map<string, Order> | Order;

//
// GET /clob/openOrders
//

export type SerumGetOpenOrdersRequest = NetworkSelectionRequest & {};

export type SerumGetOpenOrdersResponse = Map<string, Order> | Order;

//
// DELETE /clob/openOrders
//

export type SerumDeleteOpenOrdersRequest = NetworkSelectionRequest & {};

export type SerumDeleteOpenOrdersResponse = Map<string, Order> | Order;

//
// GET /clob/filledOrders
//

export type SerumGetFilledOrdersRequest = NetworkSelectionRequest & {};

export type SerumGetFilledOrdersResponse = Map<string, Order> | Order;
