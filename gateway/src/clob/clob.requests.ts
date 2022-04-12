import {
  SerumCancelOpenOrdersRequest,
  SerumCancelOpenOrdersResponse,
  SerumCancelOrdersRequest,
  SerumCancelOrdersResponse,
  SerumGetFilledOrdersRequest,
  SerumGetFilledOrdersResponse,
  SerumGetMarketsRequest,
  SerumGetMarketsResponse,
  SerumGetOpenOrdersRequest,
  SerumGetOpenOrdersResponse,
  SerumGetOrderBooksRequest,
  SerumGetOrderBooksResponse,
  SerumGetOrdersRequest,
  SerumGetOrdersResponse,
  SerumGetTickersRequest,
  SerumGetTickersResponse,
  SerumCreateOrdersRequest,
  SerumCreateOrdersResponse,
} from '../connectors/serum/serum.requests';

export type ClobDeleteOpenOrdersRequest = SerumCancelOpenOrdersRequest;
export type ClobDeleteOpenOrdersResponse = SerumCancelOpenOrdersResponse;
export type ClobDeleteOrdersRequest = SerumCancelOrdersRequest;
export type ClobDeleteOrdersResponse = SerumCancelOrdersResponse;
export type ClobGetFilledOrdersRequest = SerumGetFilledOrdersRequest;
export type ClobGetFilledOrdersResponse = SerumGetFilledOrdersResponse;
export type ClobGetOpenOrdersRequest = SerumGetOpenOrdersRequest;
export type ClobGetOpenOrdersResponse = SerumGetOpenOrdersResponse;
export type ClobGetMarketsRequest = SerumGetMarketsRequest;
export type ClobGetMarketsResponse = SerumGetMarketsResponse;
export type ClobGetOrderBooksRequest = SerumGetOrderBooksRequest;
export type ClobGetOrderBooksResponse = SerumGetOrderBooksResponse;
export type ClobPostOrdersRequest = SerumCreateOrdersRequest;
export type ClobPostOrdersResponse = SerumCreateOrdersResponse;
export type ClobGetTickersRequest = SerumGetTickersRequest;
export type ClobGetTickersResponse = SerumGetTickersResponse;
export type ClobGetOrdersRequest = SerumGetOrdersRequest;
export type ClobGetOrdersResponse = SerumGetOrdersResponse;
