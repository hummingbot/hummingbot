import { NetworkSelectionRequest } from '../../services/common-interfaces';
import {
  GetOrderBooksRequest,
  GetOrderBooksResponse,
  GetMarketsRequest,
  GetMarketsResponse,
  GetTickersRequest,
  GetTickersResponse,
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

export type RippleGetOrderBooksRequest = NetworkSelectionRequest &
  GetOrderBooksRequest;

export type RippleGetOrderBooksResponse = GetOrderBooksResponse;
