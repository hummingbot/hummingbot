import {
  SerumDeleteOpenOrdersRequest,
  SerumDeleteOpenOrdersResponse,
  SerumDeleteOrdersRequest,
  SerumDeleteOrdersResponse,
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
  SerumPostOrdersRequest,
  SerumPostOrdersResponse,
} from '../connectors/serum/serum.requests';

export type ClobDeleteOpenOrdersRequest = SerumDeleteOpenOrdersRequest;
export const ClobDeleteOpenOrdersRequest = SerumDeleteOpenOrdersRequest;
export type ClobDeleteOpenOrdersResponse = SerumDeleteOpenOrdersResponse;
export type ClobDeleteOrdersRequest = SerumDeleteOrdersRequest;
export type ClobDeleteOrdersResponse = SerumDeleteOrdersResponse;
export type ClobGetFilledOrdersRequest = SerumGetFilledOrdersRequest;
export type ClobGetFilledOrdersResponse = SerumGetFilledOrdersResponse;
export type ClobGetOpenOrdersRequest = SerumGetOpenOrdersRequest;
export type ClobGetOpenOrdersResponse = SerumGetOpenOrdersResponse;
export type ClobGetMarketsRequest = SerumGetMarketsRequest;
export type ClobGetMarketsResponse = SerumGetMarketsResponse;
export const ClobGetMarketsResponse = SerumGetMarketsResponse;
export type ClobGetOrderBooksRequest = SerumGetOrderBooksRequest;
export type ClobGetOrderBooksResponse = SerumGetOrderBooksResponse;
export type ClobPostOrdersRequest = SerumPostOrdersRequest;
export type ClobPostOrdersResponse = SerumPostOrdersResponse;
export type ClobGetTickersRequest = SerumGetTickersRequest;
export type ClobGetTickersResponse = SerumGetTickersResponse;
export type ClobGetOrdersRequest = SerumGetOrdersRequest;
export type ClobGetOrdersResponse = SerumGetOrdersResponse;