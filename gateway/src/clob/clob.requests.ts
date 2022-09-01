import {
  SerumCancelOrdersRequest,
  SerumCancelOrdersResponse,
  SerumCreateOrdersRequest,
  SerumCreateOrdersResponse,
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
  SerumPostSettleFundsRequest,
  SerumPostSettleFundsResponse,
} from '../connectors/serum/serum.requests';

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
export type ClobPostSettleFundsRequest = SerumPostSettleFundsRequest;
export type ClobPostSettleFundsResponse = SerumPostSettleFundsResponse;
