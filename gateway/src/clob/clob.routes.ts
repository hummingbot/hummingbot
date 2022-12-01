import { Request, Response, Router } from 'express';
import { StatusCodes } from 'http-status-codes';
import { Serumish } from '../connectors/serum/serum';
import { getConnector } from '../services/connection-manager';
import { asyncHandler } from '../services/error-handler';
import {
  cancelOrders,
  createOrders,
  getFilledOrders,
  getMarkets,
  getOpenOrders,
  getOrderBooks,
  getOrders,
  getTickers,
  settleFunds,
} from './clob.controllers';
import {
  ClobDeleteOrdersRequest,
  ClobDeleteOrdersResponse,
  ClobGetFilledOrdersRequest,
  ClobGetFilledOrdersResponse,
  ClobGetMarketsRequest,
  ClobGetMarketsResponse,
  ClobGetOpenOrdersRequest,
  ClobGetOpenOrdersResponse,
  ClobGetOrderBooksRequest,
  ClobGetOrderBooksResponse,
  ClobGetOrdersRequest,
  ClobGetOrdersResponse,
  ClobGetTickersRequest,
  ClobGetTickersResponse,
  ClobPostOrdersRequest,
  ClobPostOrdersResponse,
  ClobPostSettleFundsRequest,
  ClobPostSettleFundsResponse,
} from './clob.requests';

export namespace ClobRoutes {
  export const router = Router();

  router.get(
    '/',
    asyncHandler(
      async (request: Request<any>, response: Response<any, any>) => {
        const connector = await getConnector<Serumish>(
          request.body.chain,
          request.body.network,
          request.body.connector
        );

        response.status(StatusCodes.OK).json({
          chain: connector.chain,
          network: connector.network,
          connector: connector.connector,
          connection: connector.ready(),
          timestamp: Date.now(),
        });
      }
    )
  );

  router.get(
    '/markets',
    asyncHandler(
      async (
        request: Request<any, any, ClobGetMarketsRequest>,
        response: Response<ClobGetMarketsResponse, any>
      ) => {
        const result = await getMarkets(request.body);

        response.status(result.status).send(result.body);
      }
    )
  );

  /**
   * Returns the last traded prices.
   */
  router.get(
    '/tickers',
    asyncHandler(
      async (
        request: Request<any, any, ClobGetTickersRequest>,
        response: Response<ClobGetTickersResponse, any>
      ) => {
        const result = await getTickers(request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orderBooks',
    asyncHandler(
      async (
        request: Request<any, any, ClobGetOrderBooksRequest>,
        response: Response<ClobGetOrderBooksResponse, any>
      ) => {
        const result = await getOrderBooks(request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orders',
    asyncHandler(
      async (
        request: Request<any, any, ClobGetOrdersRequest>,
        response: Response<ClobGetOrdersResponse, any>
      ) => {
        const result = await getOrders(request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.post(
    '/orders',
    asyncHandler(
      async (
        request: Request<any, any, ClobPostOrdersRequest>,
        response: Response<ClobPostOrdersResponse, any>
      ) => {
        const result = await createOrders(request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.delete(
    '/orders',
    asyncHandler(
      async (
        request: Request<any, any, ClobDeleteOrdersRequest>,
        response: Response<ClobDeleteOrdersResponse, any>
      ) => {
        const result = await cancelOrders(request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orders/open',
    asyncHandler(
      async (
        request: Request<any, any, ClobGetOpenOrdersRequest>,
        response: Response<ClobGetOpenOrdersResponse, any>
      ) => {
        const result = await getOpenOrders(request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orders/filled',
    asyncHandler(
      async (
        request: Request<any, any, ClobGetFilledOrdersRequest>,
        response: Response<ClobGetFilledOrdersResponse, any>
      ) => {
        const result = await getFilledOrders(request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.post(
    '/settleFunds',
    asyncHandler(
      async (
        request: Request<any, any, ClobPostSettleFundsRequest>,
        response: Response<ClobPostSettleFundsResponse, any>
      ) => {
        const result = await settleFunds(request.body);

        response.status(result.status).json(result.body);
      }
    )
  );
}
