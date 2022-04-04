import { Request, Response, Router } from 'express';
import { asyncHandler } from '../../services/error-handler';
import { verifySolanaIsAvailable } from '../../chains/solana/solana-middlewares';
import { verifySerumIsAvailable } from './serum-middlewares';
import { SolanaConfig } from '../../chains/solana/solana.config';
import { Solana } from '../../chains/solana/solana';
import { validatePublicKey } from '../../chains/solana/solana.validators';
import {
  deleteOpenOrders,
  deleteOrders,
  getFilledOrders,
  getMarkets,
  getOpenOrders,
  getOrderBooks,
  getOrders,
  getTickers,
  postOrders,
} from './serum.controllers';
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
} from './serum.requests';
import { Serum } from './serum';

export namespace MangoRoutes {
  export const router = Router();
  export const solana = Solana.getInstance();
  export const serum = Serum.getInstance();

  router.use(
    asyncHandler(verifySolanaIsAvailable),
    asyncHandler(verifySerumIsAvailable)
  );

  router.get('/', async (_request: Request, response: Response) => {
    response.status(200).json({
      network: SolanaConfig.config.network.slug,
      connection: serum.ready,
      timestamp: Date.now(),
    });
  });

  router.get(
    '/markets',
    asyncHandler(
      async (
        request: Request<unknown, unknown, SerumGetMarketsRequest>,
        response: Response<SerumGetMarketsResponse, any>
      ) => {
        const result = await getMarkets(solana, serum, request.body);

        response.status(result.status).json(result);
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
        request: Request<unknown, unknown, SerumGetTickersRequest>,
        response: Response<SerumGetTickersResponse, any>
      ) => {
        response
          .status(200)
          .json(await getTickers(solana, serum, request.body));
      }
    )
  );

  router.get(
    '/orderBooks',
    asyncHandler(
      async (
        request: Request<unknown, unknown, SerumGetOrderBooksRequest>,
        response: Response<SerumGetOrderBooksResponse, any>
      ) => {
        // TODO: 404 if requested market does not exist
        response
          .status(200)
          .json(await getOrderBooks(solana, serum, request.body));
      }
    )
  );

  router.get(
    '/orders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, SerumGetOrdersRequest>,
        response: Response<SerumGetOrdersResponse, any>
      ) => {
        validatePublicKey(request.body);
        response.status(200).json(await getOrders(solana, serum, request.body));
      }
    )
  );

  router.post(
    '/orders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, SerumPostOrdersRequest>,
        response: Response<SerumPostOrdersResponse, any>
      ) => {
        validatePublicKey(request.body);
        response
          .status(200)
          .json(await postOrders(solana, serum, request.body));
      }
    )
  );

  router.delete(
    '/orders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, SerumDeleteOrdersRequest>,
        response: Response<SerumDeleteOrdersResponse, any>
      ) => {
        validatePublicKey(request.body);
        response
          .status(200)
          .json(await deleteOrders(solana, serum, request.body));
      }
    )
  );

  router.get(
    '/openOrders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, SerumGetOpenOrdersRequest>,
        response: Response<SerumGetOpenOrdersResponse, any>
      ) => {
        validatePublicKey(request.body);
        response
          .status(200)
          .json(await getOpenOrders(solana, serum, request.body));
      }
    )
  );

  router.delete(
    '/openOrders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, SerumDeleteOpenOrdersRequest>,
        response: Response<SerumDeleteOpenOrdersResponse, any>
      ) => {
        validatePublicKey(request.body);
        response
          .status(200)
          .json(await deleteOpenOrders(solana, serum, request.body));
      }
    )
  );

  router.get(
    '/filledOrders',
    asyncHandler(
      async (
        request: Request<unknown, unknown, SerumGetFilledOrdersRequest>,
        response: Response<SerumGetFilledOrdersResponse, any>
      ) => {
        validatePublicKey(request.body);
        response
          .status(200)
          .json(await getFilledOrders(solana, serum, request.body));
      }
    )
  );
}
