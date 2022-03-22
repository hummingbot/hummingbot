import { Router, Request, Response } from 'express';
import { asyncHandler } from '../../services/error-handler';
import { verifySolanaIsAvailable } from '../../chains/solana/solana-middlewares';
import { verifySerumIsAvailable } from './serum-middlewares';
import { SolanaConfig } from '../../chains/solana/solana.config';
import { Solana } from '../../chains/solana/solana';
import { validatePublicKey } from '../../chains/solana/solana.validators';
import {
  deleteOrders,
  fills,
  getOrders,
  markets,
  orderbook,
  postOrder,
} from './serum.controllers';
import {
  SerumMarketsRequest,
  SerumMarketsResponse,
  SerumOrderbookRequest,
  SerumOrderbookResponse,
  SerumGetOpenOrdersRequest,
  SerumGetOpenOrdersResponse,
  SerumPostOrderRequest,
  SerumOrderResponse,
  SerumTickerResponse,
  SerumDeleteOrderRequest,
  SerumGetFillsRequest,
  SerumGetFillsResponse,
  SerumDeleteOpenOrdersRequest,
  SerumDeleteOpenOrdersResponse,
  SerumGetOrderRequest,
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
      connection: serum.ready(),
      timestamp: Date.now(),
    });
  });

  router.get(
    '/markets',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumMarketsRequest>,
        res: Response<SerumMarketsResponse, any>
      ) => {
        res.status(200).json(await markets(req.body));
      }
    )
  );

  /**
   * Returns the last traded prices.
   */
  router.get(
    '/ticker',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumMarketsRequest>,
        res: Response<SerumTickerResponse, any>
      ) => {
        res.status(200).json(await markets(req.body));
      }
    )
  );

  router.get(
    '/orderbooks',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumOrderbookRequest>,
        res: Response<SerumOrderbookResponse, any>
      ) => {
        // TODO: 404 if requested market does not exist
        res.status(200).json(await orderbook(req.body));
      }
    )
  );

  router.get(
    '/order',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumGetOrderRequest>,
        res: Response<SerumOrderResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await getOrders(req.body));
      }
    )
  );

  router.post(
    '/order',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumPostOrderRequest>,
        res: Response<SerumOrderResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await postOrder(req.body));
      }
    )
  );

  router.delete(
    '/order',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumDeleteOrderRequest>,
        res: Response<SerumOrderResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await deleteOrders(req.body));
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
        res.status(200).json(await getOrders(req.body));
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
        res.status(200).json(await deleteOrders(req.body));
      }
    )
  );

  router.get(
    '/fills',
    asyncHandler(
      async (
        req: Request<unknown, unknown, SerumGetFillsRequest>,
        res: Response<SerumGetFillsResponse, any>
      ) => {
        validatePublicKey(req.body);
        res.status(200).json(await fills(req.body));
      }
    )
  );
}
