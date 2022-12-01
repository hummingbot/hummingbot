import { Request, Response, Router } from 'express';
import { StatusCodes } from 'http-status-codes';
import { Solana } from '../../chains/solana/solana';
import { verifySolanaIsAvailable } from '../../chains/solana/solana-middlewares';
import { validatePublicKey } from '../../chains/solana/solana.validators';
import { asyncHandler } from '../../services/error-handler';
import { Serum } from './serum';
import { verifySerumIsAvailable } from './serum.middlewares';
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
} from './serum.controllers';
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
} from './serum.requests';

export namespace SerumRoutes {
  export const router = Router();

  export const getSolana = async (request: Request) =>
    await Solana.getInstance(request.body.network);

  export const getSerum = async (request: Request) =>
    await Serum.getInstance(request.body.chain, request.body.network);

  router.use(
    asyncHandler(verifySolanaIsAvailable),
    asyncHandler(verifySerumIsAvailable)
  );

  router.get(
    '/',
    asyncHandler(
      async (request: Request<any>, response: Response<any, any>) => {
        const serum = await getSerum(request);

        response.status(StatusCodes.OK).json({
          chain: serum.chain,
          network: serum.network,
          connector: serum.connector,
          connection: serum.ready(),
          timestamp: Date.now(),
        });
      }
    )
  );

  router.get(
    '/markets',
    asyncHandler(
      async (
        request: Request<any, any, SerumGetMarketsRequest>,
        response: Response<SerumGetMarketsResponse, any>
      ) => {
        const solana = await getSolana(request);
        const serum = await getSerum(request);

        const result = await getMarkets(solana, serum, request.body);

        return await response.status(result.status).json(result.body);
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
        request: Request<any, any, SerumGetTickersRequest>,
        response: Response<SerumGetTickersResponse, any>
      ) => {
        const solana = await getSolana(request);
        const serum = await getSerum(request);

        const result = await getTickers(solana, serum, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orderBooks',
    asyncHandler(
      async (
        request: Request<any, any, SerumGetOrderBooksRequest>,
        response: Response<SerumGetOrderBooksResponse, any>
      ) => {
        const solana = await getSolana(request);
        const serum = await getSerum(request);

        const result = await getOrderBooks(solana, serum, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orders',
    asyncHandler(
      async (
        request: Request<any, any, SerumGetOrdersRequest>,
        response: Response<SerumGetOrdersResponse, any>
      ) => {
        const solana = await getSolana(request);
        const serum = await getSerum(request);

        validatePublicKey(request.body);

        const result = await getOrders(solana, serum, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.post(
    '/orders',
    asyncHandler(
      async (
        request: Request<any, any, SerumCreateOrdersRequest>,
        response: Response<SerumCreateOrdersResponse, any>
      ) => {
        const solana = await getSolana(request);
        const serum = await getSerum(request);

        validatePublicKey(request.body);

        const result = await createOrders(solana, serum, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.delete(
    '/orders',
    asyncHandler(
      async (
        request: Request<any, any, SerumCancelOrdersRequest>,
        response: Response<SerumCancelOrdersResponse, any>
      ) => {
        const solana = await getSolana(request);
        const serum = await getSerum(request);

        validatePublicKey(request.body);

        const result = await cancelOrders(solana, serum, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orders/open',
    asyncHandler(
      async (
        request: Request<any, any, SerumGetOpenOrdersRequest>,
        response: Response<SerumGetOpenOrdersResponse, any>
      ) => {
        const solana = await getSolana(request);
        const serum = await getSerum(request);

        validatePublicKey(request.body);

        const result = await getOpenOrders(solana, serum, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.get(
    '/orders/filled',
    asyncHandler(
      async (
        request: Request<any, any, SerumGetFilledOrdersRequest>,
        response: Response<SerumGetFilledOrdersResponse, any>
      ) => {
        const solana = await getSolana(request);
        const serum = await getSerum(request);

        validatePublicKey(request.body);

        const result = await getFilledOrders(solana, serum, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );

  router.post(
    '/settleFunds',
    asyncHandler(
      async (
        request: Request<any, any, SerumPostSettleFundsRequest>,
        response: Response<SerumPostSettleFundsResponse, any>
      ) => {
        const solana = await getSolana(request);
        const serum = await getSerum(request);

        validatePublicKey(request.body);

        const result = await settleFunds(solana, serum, request.body);

        response.status(result.status).json(result.body);
      }
    )
  );
}
