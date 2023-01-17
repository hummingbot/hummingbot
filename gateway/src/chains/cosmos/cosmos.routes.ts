/* eslint-disable @typescript-eslint/ban-types */
import { NextFunction, Router, Request, Response } from 'express';
import { verifyCosmosIsAvailable } from './cosmos-middlewares';
import { asyncHandler } from '../../services/error-handler';
import { Cosmos } from './cosmos';
import { balances, poll } from './cosmos.controllers';
import {
  CosmosBalanceResponse,
  CosmosBalanceRequest,
  CosmosPollRequest,
  CosmosPollResponse,
} from './cosmos.requests';
import {
  validateCosmosBalanceRequest,
  validateCosmosPollRequest,
} from './cosmos.validators';

export namespace CosmosRoutes {
  export const router = Router();
  export const getCosmos = async (request: Request) => {
    const cosmos = await Cosmos.getInstance(request.body.network);
    await cosmos.init();

    return cosmos;
  };

  router.use(asyncHandler(verifyCosmosIsAvailable));

  router.get(
    '/',
    asyncHandler(async (_req: Request, res: Response) => {
      const { rpcUrl, chain } = await getCosmos(_req);

      res.status(200).json({
        network: chain,
        rpcUrl: rpcUrl,
        connection: true,
        timestamp: Date.now(),
      });
    })
  );

  // Get balance for wallet
  router.post(
    '/balances',
    asyncHandler(
      async (
        req: Request<{}, {}, CosmosBalanceRequest>,
        res: Response<CosmosBalanceResponse | string, {}>,
        _next: NextFunction
      ) => {
        const cosmos = await getCosmos(req);
        validateCosmosBalanceRequest(req.body);
        res.status(200).json(await balances(cosmos, req.body));
      }
    )
  );

  // Gets status information about given transaction hash
  router.post(
    '/poll',
    asyncHandler(
      async (
        req: Request<{}, {}, CosmosPollRequest>,
        res: Response<CosmosPollResponse, {}>
      ) => {
        const cosmos = await getCosmos(req);

        validateCosmosPollRequest(req.body);
        res.status(200).json(await poll(cosmos, req.body));
      }
    )
  );
}
