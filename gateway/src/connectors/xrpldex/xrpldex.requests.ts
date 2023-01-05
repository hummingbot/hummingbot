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
} from './xrpldex.types';

//
// GET /xrpldex/markets
//
export type XRPLGetMarketsRequest = NetworkSelectionRequest & GetMarketsRequest;

export type XRPLGetMarketsResponse = GetMarketsResponse;

//
// GET /xrpldex/tickers
//
export type XRPLGetTickersRequest = NetworkSelectionRequest & GetTickersRequest;

export type XRPLGetTickersResponse = GetTickersResponse;

//
// GET /xrpldex/orders
//

export type XRPLGetOrdersRequest = NetworkSelectionRequest & GetOrdersRequest;

export type XRPLGetOrdersResponse = GetOrdersResponse;

//
// GET /xrpldex/orderBooks
//

export type XRPLGetOrderBooksRequest = NetworkSelectionRequest &
  GetOrderBooksRequest;

export type XRPLGetOrderBooksResponse = GetOrderBooksResponse;

//
// POST /xrpldex/orders
//

export type XRPLCreateOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CreateOrderRequest; waitUntilIncludedInBlock: boolean }
    | {
        orders: CreateOrderRequest[];
        waitUntilIncludedInBlock: boolean;
      }
  );

export type XRPLCreateOrdersResponse = CreateOrdersResponse;

//
// DELETE /xrpldex/orders
//

export type XRPLCancelOrdersRequest = NetworkSelectionRequest &
  (
    | { order: CancelOrderRequest; waitUntilIncludedInBlock: boolean }
    | {
        orders: CancelOrderRequest[];
        waitUntilIncludedInBlock: boolean;
      }
  );

export type XRPLCancelOrdersResponse = CancelOrdersResponse;

//
// GET /xrpldex/orders/open
//

export type XRPLGetOpenOrdersRequest = NetworkSelectionRequest &
  (
    | { order: GetOpenOrderRequest }
    | {
        orders: GetOpenOrderRequest[];
      }
  );

export type XRPLGetOpenOrdersResponse = GetOpenOrdersResponse;
