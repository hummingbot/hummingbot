import {NetworkSelectionRequest} from '../../services/common-interfaces';
import {
  CancelOpenOrdersRequest,
  CancelOpenOrdersResponse,
  CancelOrdersRequest,
  CancelOrdersResponse,
  CreateOrdersRequest,
  CreateOrdersResponse,
  GetFilledOrderRequest,
  GetFilledOrdersRequest,
  GetFilledOrdersResponse,
  GetMarketsRequest,
  GetMarketsResponse,
  GetOpenOrderRequest,
  GetOpenOrdersRequest,
  GetOpenOrdersResponse,
  GetOrderBooksRequest,
  GetOrderBooksResponse,
  GetOrdersRequest,
  GetOrdersResponse,
  GetTickersRequest,
  GetTickersResponse,
} from './serum.types';

//
// GET /clob/markets
//

export type SerumGetMarketsRequest = NetworkSelectionRequest &
  GetMarketsRequest;

export type SerumGetMarketsResponse = GetMarketsResponse;

//
// GET /clob/orderBooks
//

export type SerumGetOrderBooksRequest = NetworkSelectionRequest &
  GetOrderBooksRequest;

export type SerumGetOrderBooksResponse = GetOrderBooksResponse;

//
// GET /clob/tickers
//

export type SerumGetTickersRequest = NetworkSelectionRequest &
  GetTickersRequest;

export type SerumGetTickersResponse = GetTickersResponse;

//
// GET /clob/orders
//

export type SerumGetOrdersRequest = NetworkSelectionRequest &
  (
    | { order: GetOrdersRequest }
    | {
        orders: GetOrdersRequest[];
      }
  );

export type SerumGetOrdersResponse = GetOrdersResponse;

//
// POST /clob/orders
//

export type SerumCreateOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CreateOrdersRequest }
    | {
        orders: CreateOrdersRequest[];
      }
  );

// TODO avoid to have in the response fields that needs to do extra calls to the external APIS!!!
export type SerumCreateOrdersResponse = CreateOrdersResponse;

//
// DELETE /clob/orders
//

export type SerumCancelOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CancelOrdersRequest }
    | {
        orders: CancelOrdersRequest[];
      }
  );

// TODO avoid to have in the response fields that needs to do extra calls to the external APIS!!!
export type SerumCancelOrdersResponse = CancelOrdersResponse;

//
// GET /clob/openOrders
//

export type SerumGetOpenOrdersRequest = NetworkSelectionRequest &
  (
    | { ownerAddress: string }
    | { order: GetOpenOrderRequest }
    | {
        orders: GetOpenOrdersRequest[];
      }
  );

// TODO avoid to have in the response fields that needs to do extra calls to the external APIS!!!
export type SerumGetOpenOrdersResponse = GetOpenOrdersResponse;

//
// DELETE /clob/openOrders
//

export type SerumCancelOpenOrdersRequest = NetworkSelectionRequest &
  (
    | { ownerAddress: string }
    | { order: CancelOpenOrdersRequest }
    | {
        orders: CancelOpenOrdersRequest[];
      }
  );

export type SerumCancelOpenOrdersResponse = CancelOpenOrdersResponse;

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

// TODO avoid to have in the response fields that needs to do extra calls to the external APIS!!!
export type SerumGetFilledOrdersResponse = GetFilledOrdersResponse;
