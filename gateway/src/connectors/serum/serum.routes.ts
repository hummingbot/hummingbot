import {Request, Response, Router} from 'express';
import {asyncHandler} from '../../services/error-handler';
import {verifySolanaIsAvailable} from '../../chains/solana/solana-middlewares';
import {verifySerumIsAvailable} from './serum-middlewares';
import {SolanaConfig} from '../../chains/solana/solana.config';
import {Solana} from '../../chains/solana/solana';
import {validatePublicKey} from '../../chains/solana/solana.validators';
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

  router.get('/', async (_req: Request, res: Response) => {
    res.status(200).json({
      network: SolanaConfig.config.network.slug,
      connection: serum.ready,
      timestamp: Date.now(),
    });
  });

  router.get(
    '/markets',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumGetMarketsRequest>,
        res: Response<SerumGetMarketsResponse, any>
      ) => {
        res.status(200).json(await getMarkets(solana, serum, req.body));
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
        req: Request<unknown, unknown, SerumGetTickersRequest>,
        res: Response<SerumGetTickersResponse, any>
      ) => {
        res.status(200).json(await getTickers(solana, serum, req.body));
      }
    )
  );

  router.get(
    '/orderBooks',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumGetOrderBooksRequest>,
        res: Response<SerumGetOrderBooksResponse, any>
      ) => {
        // TODO: 404 if requested market does not exist
        res.status(200).json(await getOrderBooks(solana, serum, req.body));
      }
    )
  );

  router.get(
    '/orders',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumGetOrdersRequest>,
        res: Response<SerumGetOrdersResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await getOrders(solana, serum, req.body));
      }
    )
  );

  router.post(
    '/orders',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumPostOrdersRequest>,
        res: Response<SerumPostOrdersResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await postOrders(solana, serum, req.body));
      }
    )
  );

  router.delete(
    '/orders',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumDeleteOrdersRequest>,
        res: Response<SerumDeleteOrdersResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await deleteOrders(solana, serum, req.body));
      }
    )
  );

  router.get(
    '/openOrders',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumGetOpenOrdersRequest>,
        res: Response<SerumGetOpenOrdersResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await getOpenOrders(solana, serum, req.body));
      }
    )
  );

  router.delete(
    '/openOrders',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumDeleteOpenOrdersRequest>,
        res: Response<SerumDeleteOpenOrdersResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await deleteOpenOrders(solana, serum, req.body));
      }
    )
  );

  router.get(
    '/filledOrders',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumGetFilledOrdersRequest>,
        res: Response<SerumGetFilledOrdersResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await getFilledOrders(solana, serum, req.body));
      }
    )
  );
}
