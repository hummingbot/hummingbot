import { NetworkSelectionRequest } from '../../services/common-interfaces';
import {
  GetOrderBooksRequest,
  GetOrderBooksResponse,
  GetMarketsRequest,
  GetMarketsResponse,
  GetTickersRequest,
  GetTickersResponse,
  CreateOrdersResponse,
  CancelOrderRequest,
  CreateOrderRequest,
  CancelOrdersResponse,
  GetOpenOrderRequest,
  GetOpenOrdersResponse,
  GetOrdersRequest,
  GetOrdersResponse,
} from './rippledex.types';

//
// GET /ripple/markets
//
export type RippleGetMarketsRequest = NetworkSelectionRequest &
  GetMarketsRequest;

export type RippleGetMarketsResponse = GetMarketsResponse;

//
// GET /ripple/tickers
//
export type RippleGetTickersRequest = NetworkSelectionRequest &
  GetTickersRequest;

export type RippleGetTickersResponse = GetTickersResponse;

//
// GET /ripple/orders
//

export type RippleGetOrdersRequest = NetworkSelectionRequest & GetOrdersRequest;

export type RippleGetOrdersResponse = GetOrdersResponse;

//
// GET /ripple/orderBooks
//

export type RippleGetOrderBooksRequest = NetworkSelectionRequest &
  GetOrderBooksRequest;

export type RippleGetOrderBooksResponse = GetOrderBooksResponse;

//
// POST /ripple/orders
//

export type RippleCreateOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CreateOrderRequest; waitUntilIncludedInBlock: boolean }
    | {
        orders: CreateOrderRequest[];
        waitUntilIncludedInBlock: boolean;
      }
  );

export type RippleCreateOrdersResponse = CreateOrdersResponse;

//
// DELETE /ripple/orders
//

export type RippleCancelOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CancelOrderRequest; waitUntilIncludedInBlock: boolean }
    | {
        orders: CancelOrderRequest[];
        waitUntilIncludedInBlock: boolean;
      }
  );

export type RippleCancelOrdersResponse = CancelOrdersResponse;

//
// GET /ripple/orders/open
//

export type RippleGetOpenOrdersRequest = NetworkSelectionRequest &
  (
    | { order: GetOpenOrderRequest }
    | {
        orders: GetOpenOrderRequest[];
      }
  );

export type RippleGetOpenOrdersResponse = GetOpenOrdersResponse;
