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
    | { order: CreateOrderRequest }
    | {
        orders: CreateOrderRequest[];
      }
  );

export type RippleCreateOrdersResponse = CreateOrdersResponse;

//
// DELETE /ripple/orders
//

export type RippleCancelOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CancelOrderRequest }
    | {
        orders: CancelOrderRequest[];
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
