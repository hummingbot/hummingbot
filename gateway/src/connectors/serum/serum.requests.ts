import { NetworkSelectionRequest } from '../../services/common-interfaces';
import {
  CancelOrderRequest,
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
  GetOrderRequest,
  GetOrdersRequest,
  GetOrdersResponse,
  GetTickersRequest,
  GetTickersResponse,
  SettleFundsRequest,
  SettleFundsResponse,
} from './serum.types';

//
// GET /serum/markets
//

export type SerumGetMarketsRequest = NetworkSelectionRequest &
  GetMarketsRequest;

export type SerumGetMarketsResponse = GetMarketsResponse;

//
// GET /serum/orderBooks
//

export type SerumGetOrderBooksRequest = NetworkSelectionRequest &
  GetOrderBooksRequest;

export type SerumGetOrderBooksResponse = GetOrderBooksResponse;

//
// GET /serum/tickers
//

export type SerumGetTickersRequest = NetworkSelectionRequest &
  GetTickersRequest;

export type SerumGetTickersResponse = GetTickersResponse;

//
// GET /serum/orders
//

export type SerumGetOrdersRequest = NetworkSelectionRequest &
  (
    | { ownerAddress: string }
    | { order: GetOrderRequest }
    | {
        orders: GetOrdersRequest[];
      }
  );

export type SerumGetOrdersResponse = GetOrdersResponse;

//
// POST /serum/orders
//

export type SerumCreateOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CreateOrdersRequest }
    | {
        orders: CreateOrdersRequest[];
      }
  );

export type SerumCreateOrdersResponse = CreateOrdersResponse;

//
// DELETE /serum/orders
//

export type SerumCancelOrdersRequest = NetworkSelectionRequest &
  (
    | { ownerAddress: string }
    | { order: CancelOrderRequest }
    | {
        orders: CancelOrdersRequest[];
      }
  );

export type SerumCancelOrdersResponse = CancelOrdersResponse;

//
// GET /serum/orders/open
//

export type SerumGetOpenOrdersRequest = NetworkSelectionRequest &
  (
    | { ownerAddress: string }
    | { order: GetOpenOrderRequest }
    | {
        orders: GetOpenOrdersRequest[];
      }
  );

export type SerumGetOpenOrdersResponse = GetOpenOrdersResponse;

//
// GET /serum/orders/filled
//

export type SerumGetFilledOrdersRequest = NetworkSelectionRequest &
  (
    | { ownerAddress: string }
    | { order: GetFilledOrderRequest }
    | {
        orders: GetFilledOrdersRequest[];
      }
  );

export type SerumGetFilledOrdersResponse = GetFilledOrdersResponse;

//
// POST /serum/settleFunds
//

export type SerumPostSettleFundsRequest = NetworkSelectionRequest &
  SettleFundsRequest;

export type SerumPostSettleFundsResponse = SettleFundsResponse;
