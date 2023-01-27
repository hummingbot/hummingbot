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

import { NetworkSelectionRequest } from '../services/common-interfaces';
import { OrderType, Side } from '../amm/amm.requests';
import { Orderbook, SpotMarket } from '@injectivelabs/sdk-ts';

export interface ClobMarketsRequest extends NetworkSelectionRequest {
  market?: string;
}

export interface CLOBMarkets {
  [key: string]: SpotMarket;
}
export interface ClobMarketResponse {
  network: string;
  timestamp: number;
  latency: number;
  markets: CLOBMarkets;
}

export type ClobTickerRequest = ClobMarketsRequest;

export type ClobTickerResponse = ClobMarketResponse;

export interface ClobOrderbookRequest extends ClobMarketsRequest {
  market: string;
}

export interface ClobOrderbookResponse {
  network: string;
  timestamp: number;
  latency: number;
  orderbook: Orderbook;
}

export interface ClobGetOrderRequest extends ClobOrderbookRequest {
  address: string;
  orderId: string;
}

export interface ClobGetOrderResponse {
  network: string;
  timestamp: number;
  latency: number;
  orders:
    | [
        {
          [key: string]: string;
        }
      ]
    | [];
}

export interface CreateOrderParam {
  price: string;
  amount: string;
  orderType: OrderType;
  side: Side;
  market: string;
}

export interface ClobPostOrderRequest
  extends NetworkSelectionRequest,
    CreateOrderParam {
  address: string;
}

export interface ClobDeleteOrderRequestExtract {
  market: string;
  orderId: string;
}

export interface ClobBatchUpdateRequest extends NetworkSelectionRequest {
  address: string;
  createOrderParams?: CreateOrderParam[];
  cancelOrderParams?: ClobDeleteOrderRequestExtract[];
}

export interface ClobPostOrderResponse {
  network: string;
  timestamp: number;
  latency: number;
  txHash: string;
}

export type ClobDeleteOrderRequest = ClobGetOrderRequest;

export type ClobDeleteOrderResponse = ClobPostOrderResponse;

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
